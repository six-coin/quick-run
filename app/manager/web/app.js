(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  // 字段名到输入框 id 的映射，用于把校验错误标到正确的控件上。
  const FIELD_INPUTS = {
    display: 'f-display',
    keywords: 'f-keywords',
    path: 'f-path',
    dir: 'f-dir',
    url: 'f-url',
    command: 'f-command',
  };

  const MODAL_EXIT_MS = 170;

  const state = {
    data: null,
    settings: null,
    strings: {},
    language: 'zh-CN',
    filter: '',
    collapsed: new Set(),
    dragging: null,
    bound: false,
    lastSelection: '',
    suppressClickUntil: 0,
    // 打开的弹窗按层记录，栈顶就是最上面那一层。叠着开（设置 → 使用说明）时
    // Esc 只关掉最上面一层，关完之后下面的那层还在，背景也仍然不可交互。
    modals: [],
  };

  const pending = new Map();
  const modalTimers = new Map();
  let toastTimer = null;
  let confirmAction = null;

  // -- 桥接 ---------------------------------------------------------------
  function bridge() {
    return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
  }

  async function call(method) {
    const api = bridge();
    if (!api) return null;
    const args = Array.prototype.slice.call(arguments, 1);
    try {
      return await api[method].apply(api, args);
    } catch (error) {
      console.error(method, error);
      toast(T('manager.action_failed', { error: error }), false);
      return null;
    }
  }

  // -- 文案 ---------------------------------------------------------------
  function T(key, params) {
    const text = state.strings[key];
    if (text === undefined) return key;
    if (!params) return text;
    return text.replace(/\{(\w+)\}/g, function (match, name) {
      return Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match;
    });
  }

  async function loadStrings() {
    const payload = await call('get_strings');
    if (!payload) return;
    state.strings = payload.strings || {};
    state.language = payload.language || 'zh-CN';
  }

  /** 把静态标记上的文案全部换成当前语言。 */
  function applyStrings() {
    document.querySelectorAll('[data-i18n]').forEach(function (element) {
      element.textContent = T(element.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (element) {
      element.placeholder = T(element.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(function (element) {
      element.title = T(element.dataset.i18nTitle);
    });
    document.querySelectorAll('[data-i18n-aria]').forEach(function (element) {
      element.setAttribute('aria-label', T(element.dataset.i18nAria));
    });

    document.title = T('manager.title');
    document.documentElement.lang = state.language;
    $('list').setAttribute('aria-label', T('manager.list_label'));

    renderDepthHint();
    renderSettingsHints();
    syncSecretToggles();
    updatePathPlaceholders();
  }

  function renderDepthHint() {
    const navigation = state.data ? state.data.navigation : { max_depth: 5, max_entries: 100 };
    $('depth-hint').textContent = T('manager.depth_hint', {
      max: navigation.max_depth,
      max_entries: navigation.max_entries,
    });
  }

  // -- 延迟写入 -----------------------------------------------------------
  function queue(key, exec, delay) {
    const existing = pending.get(key);
    if (existing) clearTimeout(existing.timer);
    const timer = setTimeout(function () {
      pending.delete(key);
      exec();
    }, delay || 80);
    pending.set(key, { timer: timer, exec: exec });
  }

  async function flushPending() {
    const jobs = [];
    Array.from(pending.entries()).forEach(function (entry) {
      const key = entry[0];
      const item = entry[1];
      clearTimeout(item.timer);
      pending.delete(key);
      jobs.push(item.exec());
    });
    await Promise.all(jobs);
  }

  // -- 取值助手 -----------------------------------------------------------
  function selection() {
    return state.data ? state.data.selection : { kind: 'none', group: 0, index: 0 };
  }

  function currentGroup() {
    const sel = selection();
    if (!state.data || sel.group < 0 || sel.group >= state.data.groups.length) return null;
    return state.data.groups[sel.group];
  }

  function currentOperation() {
    const sel = selection();
    if (sel.kind !== 'operation') return null;
    const group = currentGroup();
    if (!group || sel.index < 0 || sel.index >= group.operations.length) return null;
    return group.operations[sel.index];
  }

  function keywordText(keywords) {
    const parts = String(keywords || '')
      .split('|')
      .map(function (part) {
        return part.trim();
      })
      .filter(Boolean);
    return parts.length ? parts.join(' · ') : T('manager.no_keywords');
  }

  function matches(operation, needle) {
    const haystack = (
      operation.label +
      ' ' +
      operation.keywords +
      ' ' +
      operation.type_label
    ).toLowerCase();
    return haystack.indexOf(needle) >= 0;
  }

  function visibleGroups() {
    if (!state.data) return [];
    const needle = state.filter.trim().toLowerCase();
    if (!needle) {
      return state.data.groups.map(function (group) {
        return { group: group, operations: group.operations };
      });
    }
    const result = [];
    state.data.groups.forEach(function (group) {
      const groupHit = group.name.toLowerCase().indexOf(needle) >= 0;
      const operations = groupHit
        ? group.operations
        : group.operations.filter(function (operation) {
            return matches(operation, needle);
          });
      if (operations.length || groupHit) {
        result.push({ group: group, operations: operations });
      }
    });
    return result;
  }

  function replayPanel(element) {
    element.style.animation = 'none';
    void element.offsetWidth;
    element.style.animation = '';
  }

  function svgIcon(pathData, className) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    if (className) svg.setAttribute('class', className);
    svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', pathData);
    svg.appendChild(path);
    return svg;
  }

  // -- 渲染 ---------------------------------------------------------------
  function apply(data) {
    if (!data) return;
    state.data = data;

    if (data.theme && document.documentElement.dataset.theme !== data.theme) {
      document.documentElement.dataset.theme = data.theme;
      rememberTheme(data.theme);
    }

    renderOptions(data);
    renderGroups();
    renderDetail();
    renderDirty(data.dirty);
    renderCount();

    clearInvalid();
    if (data.errors && data.errors.length) {
      data.errors.forEach(function (error) {
        markInvalid(error.field);
      });
      focusField(data.errors[0].field);
    }
    if (data.message) toast(data.message, data.ok);
  }

  function rememberTheme(theme) {
    try {
      localStorage.setItem('quickrun.theme', theme);
    } catch (error) {
      /* 隐私模式下写不进去也无所谓，只影响首帧 */
    }
  }

  /**
   * 把「值 + 文案」列表就地同步到一组按钮上。
   *
   * 这些选项的文案来自后端，切换语言后会变；但如果每次状态刷新都重建 DOM，
   * 正在聚焦的按钮会丢焦点。所以按序号复用节点，只更新 dataset 与文案。
   */
  function syncChoices(container, items, key, setup) {
    items.forEach(function (item, index) {
      let node = container.children[index];
      if (!node) {
        node = document.createElement('button');
        node.type = 'button';
        setup(node);
        container.appendChild(node);
      }
      node.dataset[key] = item.value;
      node.textContent = item.label;
    });
    while (container.childElementCount > items.length) {
      container.lastElementChild.remove();
    }
  }

  function renderOptions(data) {
    syncChoices($('type-pills'), data.types, 'type', function (button) {
      button.className = 'pill';
      button.addEventListener('click', function () {
        changeType(button.dataset.type);
      });
    });

    renderSelect('f-function', data.debug_functions);
    renderSelect('f-base-file', data.path_bases);
    renderSelect('f-base-dir', data.path_bases);
  }

  /** 把「值 + 文案」列表填进一个自绘下拉框。 */
  function renderSelect(id, items) {
    const select = $(id);
    if (!select || !items) return;
    syncChoices(select.querySelector('.select-menu'), items, 'value', function (option) {
      option.className = 'select-option';
      option.setAttribute('role', 'option');
    });
  }

  /** 让一个自绘下拉框可以展开、收起、用键盘选择。 */
  function bindSelect(id, onChoose) {
    const select = $(id);
    if (!select) return;

    select.addEventListener('click', function (event) {
      event.stopPropagation();
      const open = select.classList.toggle('open');
      select.setAttribute('aria-expanded', String(open));
    });

    select.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      const open = select.classList.toggle('open');
      select.setAttribute('aria-expanded', String(open));
    });

    select.querySelector('.select-menu').addEventListener('click', function (event) {
      const option = event.target.closest('.select-option');
      if (!option) return;
      // 不让这次点击冒泡回下拉框本身，否则会立刻又展开一次。
      event.stopPropagation();
      closeSelect(id);
      onChoose(option.dataset.value);
    });
  }

  function closeSelect(id) {
    const select = $(id);
    if (!select) return;
    select.classList.remove('open');
    select.setAttribute('aria-expanded', 'false');
  }

  function closeAllSelects() {
    document.querySelectorAll('.select.open').forEach(function (select) {
      closeSelect(select.id);
    });
  }

  function anySelectOpen() {
    return !!document.querySelector('.select.open');
  }

  /** 把下拉框的显示值与高亮同步到 ``value``。 */
  function setSelectValue(id, value) {
    const select = $(id);
    if (!select) return;
    const option = select.querySelector('.select-option[data-value="' + value + '"]');
    select.dataset.value = value;
    select.querySelector('.select-value').textContent = option ? option.textContent : value;
    select.querySelectorAll('.select-option').forEach(function (item) {
      const active = item.dataset.value === value;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', String(active));
    });
  }

  function renderGroups() {
    const list = $('list');
    // 记住焦点：每次状态变化都会重建这个子树。
    const active = document.activeElement;
    const activeId = active && list.contains(active) ? active.dataset.focusId : null;

    list.innerHTML = '';
    if (!state.data) return;

    const entries = visibleGroups();
    if (!entries.length) {
      const empty = document.createElement('div');
      empty.className = 'list-empty';
      empty.textContent = state.filter ? T('manager.no_match') : T('manager.no_operations');
      list.appendChild(empty);
      return;
    }

    const sel = selection();
    entries.forEach(function (entry) {
      const group = entry.group;
      const collapsed = state.collapsed.has(group.name);
      const section = document.createElement('section');
      section.className = 'group';
      section.dataset.group = String(group.index);
      if (!group.enabled) section.classList.add('disabled');
      if (collapsed) section.classList.add('collapsed');

      const head = document.createElement('div');
      head.className = 'group-head';
      head.dataset.group = String(group.index);
      head.dataset.node = 'group';
      head.dataset.focusId = 'head:' + group.index;
      head.draggable = !state.filter;
      head.tabIndex = -1;
      head.setAttribute('role', 'treeitem');
      head.setAttribute('aria-level', '1');
      head.setAttribute('aria-expanded', String(!collapsed));
      head.setAttribute('aria-owns', 'ops-' + group.index);
      if (sel.kind === 'group' && sel.group === group.index) head.classList.add('active');

      // 折叠箭头做成真正的按钮，它才有资格带悬浮提示；键盘操作用左右方向键，
      // 所以不占用 Tab 停靠点。
      const chevron = document.createElement('button');
      chevron.type = 'button';
      chevron.className = 'chevron-btn';
      chevron.tabIndex = -1;
      chevron.title = T('manager.expand_group');
      chevron.setAttribute('aria-label', T('manager.expand_group'));
      chevron.appendChild(svgIcon('M4 6l4 4 4-4', 'chevron'));
      chevron.addEventListener('click', function (event) {
        event.stopPropagation();
        toggleCollapse(group.name, section);
        head.focus();
      });
      head.appendChild(chevron);

      const name = document.createElement('span');
      name.className = 'group-name';
      name.textContent = group.name;
      head.appendChild(name);

      const count = document.createElement('span');
      count.className = 'group-count';
      count.textContent = String(group.count);
      head.appendChild(count);

      const add = document.createElement('button');
      add.type = 'button';
      add.className = 'group-add';
      add.dataset.focusId = 'add:' + group.index;
      // 不占 Tab 停靠点：用左右方向键从分组标题走进来。
      add.tabIndex = -1;
      add.title = T('manager.add_to_group', { name: group.name });
      add.setAttribute('aria-label', add.title);
      add.appendChild(svgIcon('M8 3.5v9M3.5 8h9'));
      add.addEventListener('click', function (event) {
        event.stopPropagation();
        addOperation(group.index);
      });
      head.appendChild(add);

      const toggle = document.createElement('label');
      toggle.className = 'switch mini';
      toggle.title = group.enabled ? T('manager.toggle_on') : T('manager.toggle_off');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = group.enabled;
      checkbox.dataset.focusId = 'toggle:' + group.index;
      checkbox.tabIndex = -1;
      checkbox.setAttribute('aria-label', T('manager.enable_group', { name: group.name }));
      checkbox.addEventListener('click', function (event) {
        event.stopPropagation();
      });
      checkbox.addEventListener('change', function (event) {
        event.stopPropagation();
        call('set_group_enabled', group.index, checkbox.checked).then(apply);
      });
      const track = document.createElement('span');
      track.className = 'switch-track';
      toggle.appendChild(checkbox);
      toggle.appendChild(track);
      head.appendChild(toggle);

      head.addEventListener('click', function (event) {
        if (Date.now() < state.suppressClickUntil) return;
        if (event.target.closest('.switch, .group-add, .chevron-btn')) return;
        call('select_group', group.index).then(apply);
      });

      section.appendChild(head);

      const ops = document.createElement('ul');
      ops.className = 'group-ops';
      ops.dataset.group = String(group.index);
      ops.id = 'ops-' + group.index;
      ops.setAttribute('role', 'group');
      ops.setAttribute('aria-label', group.name);

      entry.operations.forEach(function (operation) {
        ops.appendChild(renderOperation(operation, sel));
      });

      section.appendChild(ops);
      list.appendChild(section);
    });

    finishListRender(activeId);
  }

  /**
   * 方向键序列里只放“看得见”的节点。
   *
   * 折叠的分组会把它的操作 display:none 掉；如果还把这些隐藏节点算进来，
   * roving tabindex 的 0 号停靠点就可能落在一个不可见的元素上——那样整张
   * 列表就一个 Tab 停靠点都没有了（全折叠时正是这个表现）。
   */
  function listNodes() {
    return Array.prototype.slice
      .call($('list').querySelectorAll('[data-node]'))
      .filter(function (node) {
        return node.offsetParent !== null;
      });
  }

  function focusNode(node) {
    if (!node) return;
    listNodes().forEach(function (other) {
      other.tabIndex = other === node ? 0 : -1;
    });
    node.focus();
  }

  /**
   * 整个列表只有一个 Tab 停靠点（roving tabindex），并把焦点放回重建前的
   * 位置——每次选择都会重建列表，不恢复的话键盘操作会断掉。
   */
  function finishListRender(activeId) {
    const list = $('list');
    const nodes = listNodes();
    if (!nodes.length) return;

    const findNode = function (key) {
      return (
        nodes.filter(function (node) {
          return node.dataset.focusId === key;
        })[0] || null
      );
    };

    let target = null;
    if (activeId) {
      const previous = list.querySelector('[data-focus-id="' + activeId + '"]');
      // 已经被折叠隐藏的节点不能当停靠点，否则整张列表就没人可聚焦了。
      if (previous && previous.dataset.node && previous.offsetParent !== null) {
        target = previous;
      }
    }
    if (!target) {
      const sel = selection();
      if (sel.kind === 'operation') {
        // 选中的操作可能被折叠起来，那就退到它所属的分组标题。
        target = findNode('op:' + sel.group + ':' + sel.index) || findNode('head:' + sel.group);
      } else {
        target = findNode('head:' + sel.group);
      }
      target = target || nodes[0];
    }
    nodes.forEach(function (node) {
      node.tabIndex = node === target ? 0 : -1;
    });

    if (!activeId) return;
    const element = list.querySelector('[data-focus-id="' + activeId + '"]');
    if (element && element.offsetParent !== null && element !== document.activeElement) {
      element.focus();
    }
  }

  function renderOperation(operation, sel) {
    const item = document.createElement('li');
    item.className = 'item';
    item.dataset.group = String(operation.group);
    item.dataset.index = String(operation.index);
    item.dataset.node = 'op';
    item.dataset.focusId = 'op:' + operation.group + ':' + operation.index;
    item.draggable = !state.filter;
    item.tabIndex = -1;
    item.setAttribute('role', 'treeitem');
    item.setAttribute('aria-level', '2');
    const selected =
      sel.kind === 'operation' &&
      sel.group === operation.group &&
      sel.index === operation.index;
    item.setAttribute('aria-selected', String(selected));
    if (selected) item.classList.add('selected');

    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.dataset.type = operation.type;

    const body = document.createElement('span');
    body.className = 'item-body';

    const title = document.createElement('span');
    title.className = 'item-title';
    title.textContent = operation.label;

    const sub = document.createElement('span');
    sub.className = 'item-sub';
    sub.textContent = keywordText(operation.keywords);

    body.appendChild(title);
    body.appendChild(sub);
    item.appendChild(dot);
    item.appendChild(body);

    item.addEventListener('click', function () {
      if (Date.now() < state.suppressClickUntil) return;
      call('select_operation', operation.group, operation.index).then(apply);
    });

    return item;
  }

  function renderDetail() {
    const operation = currentOperation();
    const group = currentGroup();
    const showGroup = !operation && group && selection().kind === 'group';

    $('placeholder').classList.toggle('hidden', !!operation || !!showGroup);
    $('editor').classList.toggle('hidden', !operation);
    $('group-editor').classList.toggle('hidden', !showGroup);

    const key = operation
      ? 'op:' + operation.group + ':' + operation.index
      : showGroup
      ? 'group:' + group.index
      : 'none';
    if (key !== state.lastSelection) {
      state.lastSelection = key;
      if (operation) replayPanel($('editor'));
      if (showGroup) replayPanel($('group-editor'));
    }

    if (showGroup) renderGroupEditor(group);
    if (operation) renderOperationEditor(operation);
  }

  function renderGroupEditor(group) {
    $('group-title').textContent = group.name;
    $('group-sub').textContent = group.enabled
      ? T('manager.group_ops', { count: group.count })
      : T('manager.group_ops_off', { count: group.count });
    $('f-group-name').value = group.name;
    $('f-group-enabled').checked = group.enabled;
    $('btn-group-up').disabled = group.index === 0;
    $('btn-group-down').disabled = group.index === state.data.groups.length - 1;
    $('btn-group-delete').disabled = state.data.groups.length <= 1;
  }

  function renderOperationEditor(operation) {
    $('editor-name').textContent = operation.label;
    const chip = $('editor-type');
    chip.textContent = operation.type_label;
    chip.dataset.type = operation.type;
    $('editor-keywords').textContent = keywordText(operation.keywords);

    document.querySelectorAll('.pill').forEach(function (pill) {
      pill.classList.toggle('active', pill.dataset.type === operation.type);
    });

    $('f-display').value = operation.display;
    $('f-keywords').value = operation.keywords;

    document.querySelectorAll('.arg-panel').forEach(function (panel) {
      panel.classList.toggle('hidden', panel.dataset.type !== operation.type);
    });

    const args = operation.arguments || {};
    $('f-path').value = args.path || '';
    $('f-no-window').checked = !!args.no_window;
    $('f-dir').value = args.dir || '';
    $('f-allow-explore').checked = args.allow_explore !== false;
    $('f-depth').value = args.explore_depth === undefined ? '0' : String(args.explore_depth);
    $('f-url').value = args.url || '';
    $('f-command').value = args.command || '';
    setSelectValue('f-function', args.function || 'restart');
    const base = args.base || 'absolute';
    setSelectValue('f-base-file', base);
    setSelectValue('f-base-dir', base);

    $('btn-up').disabled = operation.index === 0;
    $('btn-down').disabled = operation.index === currentGroup().operations.length - 1;

    updateDepthVisibility();
    updatePathPlaceholders();
  }

  /** 文件 / 文件夹路径的提示语跟着「路径基准」走，每种基准给一个像样的例子。 */
  function updatePathPlaceholders() {
    const fileBase = $('f-base-file').dataset.value || 'absolute';
    const dirBase = $('f-base-dir').dataset.value || 'absolute';
    $('f-path').placeholder = T('placeholder.path.' + fileBase);
    $('f-dir').placeholder = T('placeholder.dir.' + dirBase);
  }

  function renderDirty(dirty) {
    $('dirty-badge').classList.toggle('hidden', !dirty);
    document.title = (dirty ? '• ' : '') + T('manager.title');
  }

  function renderCount() {
    if (!state.data) return;
    const total = state.data.total;
    const groups = state.data.groups.length;
    const enabled = state.data.enabled_total;
    const shown = visibleGroups().reduce(function (sum, entry) {
      return sum + entry.operations.length;
    }, 0);

    let text;
    if (state.filter && shown !== total) {
      text = T('manager.count_filtered', { shown: shown, total: total });
    } else {
      text = T('manager.count', { total: total, groups: groups });
    }
    if (enabled !== total) text += ' · ' + T('manager.count_enabled', { count: enabled });
    $('count-label').textContent = text;
  }

  function updateDepthVisibility() {
    const allowed = $('f-allow-explore').checked;
    $('row-depth').classList.toggle('hidden', !allowed);
  }

  function updateLabel(group, index, text) {
    const label = text || T('manager.unnamed_operation');
    const item = document.querySelector(
      '.item[data-group="' + group + '"][data-index="' + index + '"] .item-title'
    );
    if (item) item.textContent = label;
    const operation = currentOperation();
    if (operation && operation.group === group && operation.index === index) {
      $('editor-name').textContent = label;
    }
  }

  function updateKeywords(group, index, text) {
    const item = document.querySelector(
      '.item[data-group="' + group + '"][data-index="' + index + '"] .item-sub'
    );
    if (item) item.textContent = keywordText(text);
    const operation = currentOperation();
    if (operation && operation.group === group && operation.index === index) {
      $('editor-keywords').textContent = keywordText(text);
    }
  }

  function markDirty() {
    if (state.data) state.data.dirty = true;
    renderDirty(true);
  }

  function clearInvalid() {
    document.querySelectorAll('.invalid').forEach(function (element) {
      element.classList.remove('invalid');
    });
  }

  function markInvalid(field) {
    const element = $(FIELD_INPUTS[field]);
    if (element) element.classList.add('invalid');
  }

  function focusField(field) {
    const element = $(FIELD_INPUTS[field]);
    if (!element) return;
    element.focus();
    if (element.select) element.select();
  }

  function toast(message, ok) {
    const element = $('toast');
    element.textContent = message;
    element.classList.remove('hidden', 'leaving');
    element.classList.toggle('error', ok === false);
    void element.offsetWidth;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      element.classList.add('leaving');
      setTimeout(function () {
        element.classList.add('hidden');
        element.classList.remove('leaving');
      }, 200);
    }, 2400);
  }

  // -- 弹窗 ---------------------------------------------------------------
  function openModal(id) {
    const element = $(id);
    if (!element) return;
    const timer = modalTimers.get(id);
    if (timer) {
      clearTimeout(timer);
      modalTimers.delete(id);
    }
    element.classList.remove('hidden', 'leaving');
    void element.offsetWidth;
    const position = state.modals.indexOf(id);
    if (position >= 0) state.modals.splice(position, 1);
    state.modals.push(id);
    // 弹窗打开时背景整体不可交互，Tab 也就进不去了。
    $('app').inert = true;
    const card = element.querySelector('.modal-card');
    if (card) card.focus();
  }

  function hideModal(id) {
    const element = $(id);
    if (!element) return;
    if (element.classList.contains('hidden') || element.classList.contains('leaving')) return;
    const timer = modalTimers.get(id);
    if (timer) clearTimeout(timer);
    element.classList.add('leaving');
    const handle = setTimeout(function () {
      modalTimers.delete(id);
      element.classList.add('hidden');
      element.classList.remove('leaving');
      const position = state.modals.indexOf(id);
      if (position >= 0) state.modals.splice(position, 1);
      if (!state.modals.length) $('app').inert = false;
    }, MODAL_EXIT_MS);
    modalTimers.set(id, handle);
  }

  /** 关闭弹窗，并释放它占着的状态。 */
  function closeModal(id) {
    if (id === 'modal-sheet') {
      closeSheet(null);
      return;
    }
    hideModal(id);
    if (id === 'modal-unsaved') call('answer_close', 'cancel');
    if (id === 'modal-confirm') confirmAction = null;
  }

  function activeModal() {
    const id = state.modals[state.modals.length - 1];
    return id ? $(id) : null;
  }

  /**
   * 点弹窗外面的空白处：等同于点「取消」。
   *
   * 设置页是例外——里面全是输入框，误点一下就丢掉整个面板太粗暴，它只认
   * 显式关闭（× / 完成 / Esc）。
   */
  function backdropClose(id) {
    if (id === 'modal-settings') return;
    closeModal(id);
  }

  function focusableIn(container) {
    const selector =
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    return Array.prototype.slice
      .call(container.querySelectorAll(selector))
      .filter(function (element) {
        return !element.disabled && element.offsetParent !== null;
      });
  }

  /** 把 Tab 限制在当前弹窗里循环。 */
  function trapTab(event) {
    const modal = activeModal();
    if (!modal) return;
    const items = focusableIn(modal);
    if (!items.length) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const card = modal.querySelector('.modal-card');

    if (event.shiftKey) {
      if (document.activeElement === first || document.activeElement === card) {
        event.preventDefault();
        last.focus();
      }
    } else if (document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function askConfirm(title, text, action) {
    $('confirm-title').textContent = title;
    $('confirm-text').textContent = text;
    confirmAction = action;
    openModal('modal-confirm');
  }

  function toggleCollapse(name, section) {
    const collapsed = !state.collapsed.has(name);
    if (collapsed) state.collapsed.add(name);
    else state.collapsed.delete(name);
    section.classList.toggle('collapsed', collapsed);
    const head = section.querySelector('.group-head');
    if (head) head.setAttribute('aria-expanded', String(!collapsed));
  }

  /** 展开全部分组。 */
  function expandAll() {
    if (!state.data) return;
    state.collapsed.clear();
    renderGroups();
  }

  /** 折叠全部分组。选中项留在右侧，列表的 Tab 停靠点退到对应分组标题。 */
  function collapseAll() {
    if (!state.data) return;
    state.data.groups.forEach(function (group) {
      state.collapsed.add(group.name);
    });
    renderGroups();
  }

  function setGroupExpanded(group, expand) {
    const section = document.querySelector('.group[data-group="' + group + '"]');
    if (!section) return;
    const collapsed = section.classList.contains('collapsed');
    if (collapsed === expand) toggleCollapse(groupName(group), section);
  }

  function groupName(index) {
    const group = state.data && state.data.groups[index];
    return group ? group.name : '';
  }

  function activateNode(node) {
    if (!node || !state.data) return;

    if (node.dataset.node === 'group') {
      const index = Number(node.dataset.group);
      const section = document.querySelector('.group[data-group="' + index + '"]');
      // 折叠状态下按空格 / 回车：既刷新右侧，也把这一组展开。
      if (section && section.classList.contains('collapsed')) {
        toggleCollapse(groupName(index), section);
      }
      call('select_group', index).then(apply);
      return;
    }

    call('select_operation', Number(node.dataset.group), Number(node.dataset.index)).then(
      apply
    );
  }

  /**
   * 侧栏的方向键导航。
   *
   * 可选中的只有三种：展开的分组、折叠的分组、展开分组里的操作。
   * 加号和开关不参与——它们交给鼠标，键盘用户选中分组后在右侧面板里改，
   * 侧栏的操作因此简化成“选一个东西”这一件事。
   */
  function onListKeydown(event) {
    const node = event.target.closest('[data-node]');
    if (!node || event.target !== node) return;

    const nodes = listNodes();
    const position = nodes.indexOf(node);

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        focusNode(nodes[position + 1]);
        break;
      case 'ArrowUp':
        event.preventDefault();
        focusNode(nodes[position - 1]);
        break;
      case 'Home':
        event.preventDefault();
        focusNode(nodes[0]);
        break;
      case 'End':
        event.preventDefault();
        focusNode(nodes[nodes.length - 1]);
        break;
      case 'ArrowRight':
        event.preventDefault();
        if (node.dataset.node === 'group') {
          setGroupExpanded(Number(node.dataset.group), true);
        }
        break;
      case 'ArrowLeft':
        event.preventDefault();
        if (node.dataset.node === 'group') {
          setGroupExpanded(Number(node.dataset.group), false);
        } else {
          focusNode(
            document.querySelector(
              '.group-head[data-node="group"][data-group="' + node.dataset.group + '"]'
            )
          );
        }
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        activateNode(node);
        break;
      default:
        break;
    }
  }

  // -- 动作 ---------------------------------------------------------------
  async function save() {
    await flushPending();
    const data = await call('save');
    if (!data) return false;
    apply(data);
    return !!data.ok;
  }

  async function changeType(type) {
    const operation = currentOperation();
    if (!operation || operation.type === type) return;
    await flushPending();
    apply(await call('change_type', operation.group, operation.index, type));
  }

  async function addOperation(group) {
    await flushPending();
    state.filter = '';
    $('filter').value = '';
    $('filter-clear').classList.add('hidden');

    const data = await call('add_operation', group);
    if (!data) return;

    const target = data.groups[data.selection.group];
    if (target) state.collapsed.delete(target.name);
    apply(data);

    const item = document.querySelector('.item.selected');
    if (item) {
      item.classList.add('flash');
      item.scrollIntoView({ block: 'nearest' });
    }
    const input = $('f-display');
    if (input && !$('editor').classList.contains('hidden')) input.focus();
  }

  async function addGroup() {
    await flushPending();
    state.filter = '';
    $('filter').value = '';
    $('filter-clear').classList.add('hidden');
    apply(await call('add_group'));
    const input = $('f-group-name');
    if (input && !$('group-editor').classList.contains('hidden')) {
      input.focus();
      input.select();
    }
  }

  /**
   * 下拉框选中一项：立刻写进后端，并把同名的另一个下拉框一起对齐。
   *
   * 文件和文件夹各有自己的「路径基准」下拉框，但写的是同一个参数；
   * 切换类型时两个面板轮流出现，不一起更新就会显示上一个类型的旧值。
   */
  async function chooseArgument(key, value, selectId) {
    const operation = currentOperation();
    if (!operation) return;
    setSelectValue(selectId, value);
    if (key === 'base') {
      ['f-base-file', 'f-base-dir'].forEach(function (id) {
        setSelectValue(id, value);
      });
      updatePathPlaceholders();
    }
    await call('set_argument', operation.group, operation.index, key, value);
    markDirty();
  }

  function openGroupPicker() {
    const operation = currentOperation();
    if (!operation) return;

    const picker = $('group-picker');
    picker.innerHTML = '';
    state.data.groups.forEach(function (group) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'picker-item' + (group.index === operation.group ? ' current' : '');

      const name = document.createElement('span');
      name.textContent = group.name;
      const count = document.createElement('span');
      count.className = 'picker-count';
      count.textContent = T('manager.group_ops', { count: group.count });

      button.appendChild(name);
      button.appendChild(count);
      button.addEventListener('click', async function () {
        closeModal('modal-group');
        if (group.index === operation.group) return;
        await flushPending();
        apply(
          await call(
            'move_operation',
            operation.group,
            operation.index,
            group.index,
            group.operations.length
          )
        );
      });
      picker.appendChild(button);
    });

    openModal('modal-group');
  }

  // -- 设置 ---------------------------------------------------------------
  async function openSettings() {
    const settings = await call('get_settings');
    if (!settings) return;
    state.settings = settings;
    resetSecrets();
    renderSettings();
    openModal('modal-settings');
  }

  /** 每次打开设置都把密钥恢复成隐藏状态。 */
  function resetSecrets() {
    document.querySelectorAll('.secret').forEach(function (wrap) {
      const input = wrap.querySelector('input');
      if (input) input.type = 'password';
      wrap.classList.remove('revealed');
    });
    syncSecretToggles();
  }

  function syncSecretToggles() {
    document.querySelectorAll('.secret-toggle').forEach(function (button) {
      const input = $(button.dataset.target);
      const revealed = !!input && input.type === 'text';
      const key = revealed ? 'settings.hide_secret' : 'settings.show_secret';
      button.title = T(key);
      button.setAttribute('aria-label', T(key));
    });
  }

  function renderSettings() {
    const settings = state.settings;
    if (!settings) return;

    const seg = $('set-language');
    seg.innerHTML = '';
    settings.languages.forEach(function (item) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'seg-item' + (item.value === settings.language ? ' active' : '');
      button.textContent = item.label;
      button.setAttribute('aria-pressed', String(item.value === settings.language));
      button.addEventListener('click', function () {
        chooseLanguage(item.value);
      });
      seg.appendChild(button);
    });

    $('set-depth').value = String(settings.max_depth);
    $('set-entries').value = String(settings.max_entries);
    $('set-animation-in').value = String(settings.animation_in_ms);
    $('set-animation-out').value = String(settings.animation_out_ms);
    $('set-appid').value = settings.translate_appid || '';
    $('set-secret').value = settings.translate_secret || '';
    $('set-ai').value = settings.ai_api_key || '';
    $('set-prompt').value = settings.ai_prompt || '';
    renderAbout(settings);
    renderSettingsHints();
  }

  function renderAbout(settings) {
    $('about-version').textContent = settings.version || '';

    // 输入框显示「重启后生效的落点」，没有待生效的值就是当前目录。
    const next = settings.data_dir_next || '';
    const input = $('about-data-dir');
    input.value = next || settings.data_dir || '';
    input.title = input.value;
    $('about-data-hint').textContent = next
      ? T('about.data_dir_pending', { path: next })
      : T('about.data_dir_hint');
  }

  function renderSettingsHints() {
    if (!state.settings) return;
    $('depth-limit-hint').textContent = T('settings.max_depth_hint', {
      max: state.settings.max_depth_limit,
    });
    $('animation-hint').textContent = T('settings.animation_hint', {
      max: state.settings.animation_range[1],
    });
  }

  async function chooseLanguage(code) {
    if (!state.settings || code === state.settings.language) return;
    const data = await call('set_language', code);
    if (!data) return;
    await loadStrings();
    state.settings.language = data.language;
    applyStrings();
    apply(data);
    renderSettings();
  }

  /** 数字类设置的合法区间，由 get_settings 提供，和后端用的是同一组常量。 */
  function settingRange(key) {
    const settings = state.settings;
    if (!settings) return null;
    if (key === 'max_depth') return [0, settings.max_depth_limit];
    if (key === 'max_entries') return settings.max_entries_range;
    if (key === 'animation_in_ms' || key === 'animation_out_ms') return settings.animation_range;
    return null;
  }

  function clampSetting(key, value) {
    const range = settingRange(key);
    if (!range) return value;
    return Math.min(Math.max(value, range[0]), range[1]);
  }

  function bindSettingInput(id, key, numeric) {
    $(id).addEventListener('input', function (event) {
      const input = event.target;
      const raw = input.value;
      queue(
        'settings:' + key,
        async function () {
          let value = raw;
          if (numeric) {
            const text = String(raw).trim();
            const parsed = Number(text);
            // 空串或非数字：不写盘，把输入框拉回已保存的值。
            if (!text || !Number.isFinite(parsed)) {
              if (state.settings && input.value === raw) {
                input.value = String(state.settings[key]);
              }
              return;
            }
            // 超界直接夹回区间，输入框跟着变成真正生效的值。
            value = clampSetting(key, Math.round(parsed));
          }
          const patch = {};
          patch[key] = value;
          const data = await call('update_settings', patch);
          if (!data) return;
          if (state.data) state.data.navigation = data.navigation;
          renderDepthHint();
          if (state.settings) state.settings[key] = value;
          // 只改自己刚提交的那份内容：期间用户接着打字就别去动他的输入框。
          if (numeric && input.value === raw && raw !== String(value)) {
            input.value = String(value);
          }
        },
        500
      );
    });
  }

  // -- 绑定 ---------------------------------------------------------------
  function bind() {
    if (state.bound) return;
    state.bound = true;

    $('filter').addEventListener('input', function (event) {
      state.filter = event.target.value;
      $('filter-clear').classList.toggle('hidden', !state.filter);
      renderGroups();
      renderCount();
    });

    $('filter-clear').addEventListener('click', function () {
      state.filter = '';
      $('filter').value = '';
      $('filter-clear').classList.add('hidden');
      renderGroups();
      renderCount();
      $('filter').focus();
    });

    $('f-display').addEventListener('input', function (event) {
      const operation = currentOperation();
      if (!operation) return;
      const value = event.target.value;
      event.target.classList.remove('invalid');
      queue('field:display', function () {
        return call('set_field', operation.group, operation.index, 'display', value);
      });
      updateLabel(operation.group, operation.index, value);
      markDirty();
    });

    $('f-keywords').addEventListener('input', function (event) {
      const operation = currentOperation();
      if (!operation) return;
      const value = event.target.value;
      event.target.classList.remove('invalid');
      queue('field:keywords', function () {
        return call('set_field', operation.group, operation.index, 'keywords', value);
      });
      updateKeywords(operation.group, operation.index, value);
      markDirty();
    });

    $('f-group-name').addEventListener('input', function (event) {
      const group = currentGroup();
      if (!group || selection().kind !== 'group') return;
      const value = event.target.value;
      queue('group:name', function () {
        return call('set_group_name', group.index, value);
      });
      const head = document.querySelector(
        '.group-head[data-group="' + group.index + '"] .group-name'
      );
      if (head) head.textContent = value || T('manager.unnamed_operation');
      markDirty();
    });

    $('f-group-enabled').addEventListener('change', function (event) {
      const group = currentGroup();
      if (!group || selection().kind !== 'group') return;
      call('set_group_enabled', group.index, event.target.checked).then(apply);
    });

    document.querySelectorAll('[data-arg]').forEach(function (input) {
      const key = input.dataset.arg;
      const eventName = input.type === 'checkbox' ? 'change' : 'input';
      input.addEventListener(eventName, function () {
        const operation = currentOperation();
        if (!operation) return;
        const value = input.type === 'checkbox' ? input.checked : input.value;
        input.classList.remove('invalid');
        queue('arg:' + key, function () {
          return call('set_argument', operation.group, operation.index, key, value);
        });
        if (key === 'allow_explore') updateDepthVisibility();
        markDirty();
      });
    });

    document.querySelectorAll('[data-browse]').forEach(function (button) {
      button.addEventListener('click', async function () {
        const operation = currentOperation();
        if (!operation) return;
        const kind = button.dataset.browse;
        const selected = await call(kind === 'file' ? 'browse_file' : 'browse_dir');
        if (!selected) return;
        const input = kind === 'file' ? $('f-path') : $('f-dir');
        input.value = selected;
        await call(
          'set_argument',
          operation.group,
          operation.index,
          kind === 'file' ? 'path' : 'dir',
          selected
        );
        markDirty();
      });
    });

    bindSelect('f-function', function (value) {
      chooseArgument('function', value, 'f-function');
    });
    bindSelect('f-base-file', function (value) {
      chooseArgument('base', value, 'f-base-file');
    });
    bindSelect('f-base-dir', function (value) {
      chooseArgument('base', value, 'f-base-dir');
    });
    document.addEventListener('click', closeAllSelects);

    $('btn-move-group').addEventListener('click', openGroupPicker);

    $('btn-add-empty').addEventListener('click', function () {
      addGroup();
    });
    $('btn-add-group').addEventListener('click', function () {
      addGroup();
    });
    $('btn-expand-all').addEventListener('click', expandAll);
    $('btn-collapse-all').addEventListener('click', collapseAll);
    $('btn-group-add-op').addEventListener('click', function () {
      const group = currentGroup();
      if (group) addOperation(group.index);
    });

    $('btn-up').addEventListener('click', async function () {
      const operation = currentOperation();
      if (!operation) return;
      await flushPending();
      apply(await call('move_operation_by', operation.group, operation.index, -1));
    });

    $('btn-down').addEventListener('click', async function () {
      const operation = currentOperation();
      if (!operation) return;
      await flushPending();
      apply(await call('move_operation_by', operation.group, operation.index, 1));
    });

    $('btn-group-up').addEventListener('click', async function () {
      const group = currentGroup();
      if (!group) return;
      await flushPending();
      apply(await call('move_group_by', group.index, -1));
    });

    $('btn-group-down').addEventListener('click', async function () {
      const group = currentGroup();
      if (!group) return;
      await flushPending();
      apply(await call('move_group_by', group.index, 1));
    });

    $('btn-delete-op').addEventListener('click', function () {
      const operation = currentOperation();
      if (!operation) return;
      askConfirm(
        T('manager.delete_op_title'),
        T('manager.delete_op_text', { name: operation.label }),
        async function () {
          await flushPending();
          apply(await call('delete_operation', operation.group, operation.index));
        }
      );
    });

    $('btn-group-delete').addEventListener('click', function () {
      const group = currentGroup();
      if (!group || selection().kind !== 'group') return;
      askConfirm(
        T('manager.delete_group_title'),
        T('manager.delete_group_text', { name: group.name, count: group.count }),
        async function () {
          await flushPending();
          apply(await call('delete_group', group.index));
        }
      );
    });

    $('btn-confirm-ok').addEventListener('click', async function () {
      hideModal('modal-confirm');
      const action = confirmAction;
      confirmAction = null;
      if (action) await action();
    });
    $('btn-confirm-cancel').addEventListener('click', function () {
      confirmAction = null;
      closeModal('modal-confirm');
    });

    $('btn-unsaved-cancel').addEventListener('click', function () {
      closeModal('modal-unsaved');
    });
    $('btn-unsaved-discard').addEventListener('click', function () {
      hideModal('modal-unsaved');
      call('answer_close', 'close');
    });
    $('btn-unsaved-save').addEventListener('click', async function () {
      if (!(await save())) return;
      hideModal('modal-unsaved');
      call('answer_close', 'close');
    });

    $('btn-theme').addEventListener('click', async function () {
      const root = document.documentElement;
      const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      rememberTheme(next);
      await call('set_theme', next);
    });

    $('btn-settings').addEventListener('click', openSettings);
    $('btn-settings-done').addEventListener('click', function () {
      closeModal('modal-settings');
    });
    $('sheet-body').addEventListener('change', function (event) {
      if (event.target.id !== 'firstrun-language') return;
      previewLanguage(event.target.value);
    });

    $('btn-about-readme').addEventListener('click', openAboutReadme);
    $('btn-about-reset').addEventListener('click', confirmResetSettings);
    $('btn-prompt-reset').addEventListener('click', restoreDefaultPrompt);
    $('btn-about-data-dir').addEventListener('click', changeDataDir);
    $('btn-about-data-reset').addEventListener('click', resetDataDir);
    $('about-data-dir').addEventListener('keydown', function (event) {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      applyDataDir(event.target.value);
    });
    $('sheet-close').addEventListener('click', function () {
      closeSheet(null);
    });
    bindSettingInput('set-depth', 'max_depth', true);
    bindSettingInput('set-entries', 'max_entries', true);
    bindSettingInput('set-animation-in', 'animation_in_ms', true);
    bindSettingInput('set-animation-out', 'animation_out_ms', true);
    bindSettingInput('set-appid', 'translate_appid', false);
    bindSettingInput('set-secret', 'translate_secret', false);
    bindSettingInput('set-ai', 'ai_api_key', false);
    bindSettingInput('set-prompt', 'ai_prompt', false);

    document.querySelectorAll('.secret-toggle').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = $(button.dataset.target);
        if (!input) return;
        const reveal = input.type === 'password';
        input.type = reveal ? 'text' : 'password';
        input.parentElement.classList.toggle('revealed', reveal);
        syncSecretToggles();
        input.focus();
      });
    });

    $('btn-save').addEventListener('click', function () {
      save();
    });

    document.querySelectorAll('[data-close]').forEach(function (button) {
      button.addEventListener('click', function () {
        closeModal(button.dataset.close);
      });
    });

    // 点弹窗外面的空白处关闭。用 mousedown 而不是 click：从卡片里按下、
    // 拖到外面松开（选文字）不该被当成“点了外面”。
    document.querySelectorAll('.modal').forEach(function (modal) {
      modal.addEventListener('mousedown', function (event) {
        if (event.target !== modal) return;
        backdropClose(modal.id);
      });
    });

    document.addEventListener('keydown', function (event) {
      const modifier = event.ctrlKey || event.metaKey;

      if (event.key === 'Tab') {
        trapTab(event);
        return;
      }

      // 下拉框展开时 Esc 先收起下拉框，再按一次才轮到弹窗。
      if (event.key === 'Escape' && anySelectOpen()) {
        event.preventDefault();
        closeAllSelects();
        return;
      }

      if (modifier && event.key.toLowerCase() === 's') {
        event.preventDefault();
        save();
      } else if (modifier && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        $('filter').focus();
        $('filter').select();
      } else if (event.key === 'Escape') {
        const modal = activeModal();
        if (modal) {
          // 只关最上面一层；下面压着的弹窗保持原样。
          closeModal(modal.id);
        } else if (state.filter) {
          $('filter-clear').click();
        }
      }
    });

    const list = $('list');
    list.addEventListener('keydown', onListKeydown);

    list.addEventListener('dragstart', function (event) {
      if (state.filter) {
        event.preventDefault();
        return;
      }
      const item = event.target.closest('.item');
      const head = event.target.closest('.group-head');
      if (item) {
        state.dragging = {
          kind: 'op',
          group: Number(item.dataset.group),
          index: Number(item.dataset.index),
        };
        item.classList.add('dragging');
      } else if (head) {
        if (event.target.closest('.switch, .group-add, .chevron-btn')) {
          event.preventDefault();
          return;
        }
        state.dragging = { kind: 'group', index: Number(head.dataset.group) };
        head.parentElement.classList.add('dragging');
      }
      if (state.dragging && event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', 'drag');
      }
    });

    list.addEventListener('dragend', function () {
      state.dragging = null;
      list.querySelectorAll('.dragging').forEach(function (element) {
        element.classList.remove('dragging');
      });
      clearDropMarkers();
    });

    list.addEventListener('dragover', function (event) {
      if (!state.dragging || state.filter) return;
      event.preventDefault();
      clearDropMarkers();

      const item = event.target.closest('.item');
      const head = event.target.closest('.group-head');

      if (!item && head && state.dragging.kind === 'op') {
        head.parentElement.classList.add('drop-group');
        return;
      }

      const target = item || head;
      if (!target) return;
      if (item && state.dragging.kind !== 'op') return;

      const rect = target.getBoundingClientRect();
      const after = event.clientY > rect.top + rect.height / 2;
      target.classList.add(after ? 'drop-after' : 'drop-before');
    });

    list.addEventListener('drop', async function (event) {
      event.preventDefault();
      const dragging = state.dragging;
      state.dragging = null;
      list.querySelectorAll('.dragging').forEach(function (element) {
        element.classList.remove('dragging');
      });
      clearDropMarkers();
      if (!dragging || state.filter) return;

      state.suppressClickUntil = Date.now() + 250;
      const item = event.target.closest('.item');
      const head = event.target.closest('.group-head');

      if (dragging.kind === 'group') {
        if (!head) return;
        const rect = head.getBoundingClientRect();
        const after = event.clientY > rect.top + rect.height / 2;
        const to = Number(head.dataset.group) + (after ? 1 : 0);
        if (to === dragging.index || to === dragging.index + 1) return;
        apply(await call('move_group', dragging.index, to));
        return;
      }

      if (item) {
        const rect = item.getBoundingClientRect();
        const after = event.clientY > rect.top + rect.height / 2;
        const toGroup = Number(item.dataset.group);
        const toIndex = Number(item.dataset.index) + (after ? 1 : 0);
        if (
          toGroup === dragging.group &&
          (toIndex === dragging.index || toIndex === dragging.index + 1)
        ) {
          return;
        }
        apply(
          await call('move_operation', dragging.group, dragging.index, toGroup, toIndex)
        );
      } else if (head) {
        const toGroup = Number(head.dataset.group);
        const target = state.data.groups[toGroup];
        apply(
          await call(
            'move_operation',
            dragging.group,
            dragging.index,
            toGroup,
            target.operations.length
          )
        );
      }
    });
  }

  function clearDropMarkers() {
    document.querySelectorAll('.drop-before, .drop-after').forEach(function (element) {
      element.classList.remove('drop-before', 'drop-after');
    });
    document.querySelectorAll('.drop-group').forEach(function (element) {
      element.classList.remove('drop-group');
    });
  }

  // -- 内容弹窗与使用说明 -----------------------------------------------
  let sheetResolve = null;

  function openSheet(options) {
    return new Promise(function (resolve) {
      sheetResolve = resolve;
      $('sheet-title').textContent = options.title || '';
      $('sheet-body').innerHTML = options.html || '';
      $('sheet-body').scrollTop = 0;
      $('sheet-actions').innerHTML = '';

      (options.actions || [{ label: T('settings.done'), value: true, primary: true }]).forEach(
        function (action) {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'btn ' + (action.kind || (action.primary ? 'primary' : 'ghost'));
          button.textContent = action.label;
          button.addEventListener('click', function () {
            closeSheet(action.value);
          });
          $('sheet-actions').appendChild(button);
        }
      );

      $('sheet-close').hidden = options.dismissible === false;
      $('modal-sheet')
        .querySelector('.modal-card')
        .classList.toggle('narrow', Boolean(options.narrow));
      openModal('modal-sheet');
    });
  }

  function closeSheet(value) {
    hideModal('modal-sheet');
    const resolve = sheetResolve;
    sheetResolve = null;
    if (resolve) resolve(value);
  }

  function mdEscape(value) {
    return String(value === undefined || value === null ? '' : value).replace(
      /[&<>"']/g,
      function (char) {
        return {
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;',
        }[char];
      }
    );
  }

  function mdInline(text) {
    const codes = [];
    let out = mdEscape(text).replace(/`([^`]+)`/g, function (match, code) {
      codes.push(code);
      return '\u0000' + (codes.length - 1) + '\u0000';
    });
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1');
    out = out.replace(/\u0000(\d+)\u0000/g, function (match, index) {
      return '<code>' + codes[Number(index)] + '</code>';
    });
    return out;
  }

  function mdRow(line) {
    return line
      .trim()
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map(function (cell) {
        return cell.trim();
      });
  }

  /** 只覆盖手册里实际用到的语法：标题、段落、列表、表格、代码块、引用、分隔线。 */
  function renderMarkdown(text) {
    const lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
    const out = [];
    let paragraph = [];
    let index = 0;

    function flush() {
      if (!paragraph.length) return;
      out.push('<p>' + mdInline(paragraph.join(' ')) + '</p>');
      paragraph = [];
    }

    while (index < lines.length) {
      const line = lines[index];

      if (/^```/.test(line)) {
        flush();
        index += 1;
        const code = [];
        while (index < lines.length && !/^```/.test(lines[index])) code.push(lines[index++]);
        index += 1;
        out.push('<pre><code>' + mdEscape(code.join('\n')) + '</code></pre>');
        continue;
      }

      if (!line.trim()) {
        flush();
        index += 1;
        continue;
      }

      const heading = /^(#{1,6})\s+(.*)$/.exec(line);
      if (heading) {
        flush();
        const level = Math.min(6, heading[1].length + 1);
        out.push('<h' + level + '>' + mdInline(heading[2].trim()) + '</h' + level + '>');
        index += 1;
        continue;
      }

      if (
        /^\s*\|/.test(line) &&
        index + 1 < lines.length &&
        /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[index + 1])
      ) {
        flush();
        const header = mdRow(line);
        index += 2;
        const rows = [];
        while (index < lines.length && /^\s*\|/.test(lines[index])) rows.push(mdRow(lines[index++]));
        out.push(
          '<table><thead><tr>' +
            header
              .map(function (cell) {
                return '<th>' + mdInline(cell) + '</th>';
              })
              .join('') +
            '</tr></thead><tbody>' +
            rows
              .map(function (row) {
                return (
                  '<tr>' +
                  row
                    .map(function (cell) {
                      return '<td>' + mdInline(cell) + '</td>';
                    })
                    .join('') +
                  '</tr>'
                );
              })
              .join('') +
            '</tbody></table>'
        );
        continue;
      }

      if (/^\s*[-*]\s+/.test(line)) {
        flush();
        const items = [];
        while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
          items.push(lines[index].replace(/^\s*[-*]\s+/, ''));
          index += 1;
        }
        out.push(
          '<ul>' +
            items
              .map(function (item) {
                return '<li>' + mdInline(item) + '</li>';
              })
              .join('') +
            '</ul>'
        );
        continue;
      }

      if (/^\s*\d+\.\s+/.test(line)) {
        flush();
        const items = [];
        while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
          items.push(lines[index].replace(/^\s*\d+\.\s+/, ''));
          index += 1;
        }
        out.push(
          '<ol>' +
            items
              .map(function (item) {
                return '<li>' + mdInline(item) + '</li>';
              })
              .join('') +
            '</ol>'
        );
        continue;
      }

      if (/^>\s?/.test(line)) {
        flush();
        out.push('<blockquote>' + mdInline(line.replace(/^>\s?/, '')) + '</blockquote>');
        index += 1;
        continue;
      }

      if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) {
        flush();
        out.push('<hr>');
        index += 1;
        continue;
      }

      paragraph.push(line.trim());
      index += 1;
    }

    flush();
    return '<div class="md">' + out.join('\n') + '</div>';
  }

  async function openAboutReadme() {
    const readme = await call('get_readme');
    const body =
      readme && readme.markdown
        ? renderMarkdown(readme.markdown)
        : '<p class="hint">' + mdEscape(T('about.readme_missing')) + '</p>';
    await openSheet({
      title: T('about.readme_title'),
      html: body,
      actions: [{ label: T('settings.done'), value: true, primary: true }],
    });
  }

  /** 设置里至少填了一项凭据（翻译或查词），重置时会一起被清掉。 */
  function hasPrivateInfo(settings) {
    return Boolean(
      String(settings.translate_appid || '').trim() ||
        String(settings.translate_secret || '').trim() ||
        String(settings.ai_api_key || '').trim()
    );
  }

  async function restoreDefaultPrompt() {
    const settings = state.settings;
    if (!settings || !settings.default_ai_prompt) return;
    $('set-prompt').value = settings.default_ai_prompt;
    settings.ai_prompt = settings.default_ai_prompt;
    await call('update_settings', { ai_prompt: settings.default_ai_prompt });
    toast(T('settings.ai_prompt_restored'), true);
  }

  async function confirmResetSettings() {
    const settings = state.settings || {};
    const hasPrivate = hasPrivateInfo(settings);

    // 有凭据时多一条警告和一个「保留隐私信息」的出口：APP ID / API Key 得去
    // 别处重新申请，误删一次很麻烦。
    const actions = [{ label: T('manager.cancel'), value: 'cancel' }];
    if (hasPrivate) actions.push({ label: T('about.reset_keep_private'), value: 'keep' });
    actions.push({ label: T('about.reset'), value: 'ok', kind: 'danger' });

    let html = '<p>' + mdEscape(T('about.reset_confirm')) + '</p>';
    if (hasPrivate) {
      html += '<p class="warn">' + mdEscape(T('about.reset_confirm_private')) + '</p>';
    }

    const choice = await openSheet({
      title: T('about.reset'),
      html: html,
      narrow: true,
      actions: actions,
    });
    if (choice !== 'ok' && choice !== 'keep') return;

    const snapshot = await call('reset_settings', choice === 'keep');
    if (!snapshot) return;
    await loadStrings();
    applyStrings();
    apply(snapshot);
    const fresh = await call('get_settings');
    if (fresh) {
      state.settings = fresh;
      renderSettings();
    }
    if (snapshot.message) toast(snapshot.message, true);
  }

  async function applyDataDir(value) {
    const text = String(value || '').trim();
    if (!text) {
      renderSettings();
      return;
    }
    const snapshot = await call('set_data_dir', text);
    if (!snapshot) return;
    apply(snapshot);
    const settings = await call('get_settings');
    if (settings) {
      state.settings = settings;
      renderSettings();
    }
    if (snapshot.message) toast(snapshot.message, snapshot.ok !== false);
  }

  async function changeDataDir() {
    const settings = state.settings || {};
    const current = String(settings.data_dir_next || settings.data_dir || '').trim();
    const typed = $('about-data-dir').value.trim();
    // 输入框改过就按输入的落点走，没改过才去选目录。
    if (typed && typed !== current) {
      await applyDataDir(typed);
      return;
    }
    const picked = await call('browse_dir');
    if (!picked) return;
    await applyDataDir(picked);
  }

  async function resetDataDir() {
    const snapshot = await call('reset_data_dir');
    if (!snapshot) return;
    apply(snapshot);
    const settings = await call('get_settings');
    if (settings) {
      state.settings = settings;
      renderSettings();
    }
    if (snapshot.message) toast(snapshot.message, snapshot.ok !== false);
  }

  async function runFirstRun() {
    const data = state.data;
    const options = (data.languages || [])
      .map(function (item) {
        return (
          '<option value="' +
          mdEscape(item.value) +
          '"' +
          (item.value === data.language ? ' selected' : '') +
          '>' +
          mdEscape(item.label) +
          '</option>'
        );
      })
      .join('');

    const pending = openSheet({
      title: T('firstrun.title'),
      dismissible: false,
      html:
        '<p data-i18n="firstrun.text">' + mdEscape(T('firstrun.text')) + '</p>' +
        '<div class="field"><label for="firstrun-language" data-i18n="firstrun.title">' +
        mdEscape(T('firstrun.title')) +
        '</label><select id="firstrun-language" class="input">' +
        options +
        '</select></div>',
      actions: [{ label: T('firstrun.start'), value: 'go', primary: true }],
    });
    // 下拉框一改就把界面切成那种语言：用户不必先点「开始使用」才能看懂界面。
    const startButton = document.querySelector('#sheet-actions .btn');
    if (startButton) startButton.dataset.i18n = 'firstrun.start';
    const choice = await pending;
    if (choice !== 'go') return;

    const select = $('firstrun-language');
    const snapshot = await call('complete_first_run', select ? select.value : data.language);
    if (snapshot) {
      await loadStrings();
      applyStrings();
      apply(snapshot);
    }
    await showFirstRunReadme(data.redirected_from);
  }

  /* 首次运行的语言下拉框：只换内存里的语言，不落盘，界面立刻跟着变。 */
  async function previewLanguage(code) {
    const data = await call('preview_language', code);
    if (!data) return;
    await loadStrings();
    applyStrings();
    const title = $('sheet-title');
    if (title) title.textContent = T('firstrun.title');
    const start = document.querySelector('#sheet-actions .btn');
    if (start) start.textContent = T('firstrun.start');
  }

  async function showFirstRunReadme(redirected) {
    const readme = await call('get_readme');
    const body =
      readme && readme.markdown
        ? renderMarkdown(readme.markdown)
        : '<p class="hint">' + mdEscape(T('about.readme_missing')) + '</p>';
    const choice = await openSheet({
      title: T('firstrun.readme_title'),
      dismissible: false,
      html: '<p>' + mdEscape(T('firstrun.readme_text')) + '</p>' + body,
      actions: [{ label: T('firstrun.readme_close'), value: 'ok', primary: true }],
    });
    if (choice && redirected) showRedirectNote(redirected);
  }

  function showRedirectNote(origin) {
    const key = 'firstrun.origin.' + origin;
    const label = state.strings[key] ? T(key) : origin;
    openSheet({
      title: T('firstrun.redirect_title'),
      dismissible: false,
      html:
        '<p>' +
        mdEscape(T('firstrun.redirect_text', { origin: label, manager: T('manager.title') })) +
        '</p>',
      actions: [{ label: T('firstrun.readme_close'), value: true, primary: true }],
    });
  }

  // -- 关闭握手 -----------------------------------------------------------
  /**
   * Python 在原生 ``closing`` 回调里碰不了网页（会死锁），所以它取消关闭、
   * 从工作线程调用这个方法；用户的选择再通过 ``answer_close`` 传回去。
   */
  // 名字不用 window.app：页面里有 id="app" 的元素，浏览器会用它占住这个全局名。
  window.quickRun = {
    askUnsaved: function () {
      openModal('modal-unsaved');
      return true;
    },
  };

  // -- 启动 ---------------------------------------------------------------
  /**
   * 打开窗口就把光标放进搜索框。
   *
   * 管理器一打开，十有八九是要找一条操作；让人先点一下搜索框纯属多余。
   * 有校验错误时不抢焦点——那时焦点已经被送到出错的字段上了。
   */
  function focusSearch() {
    if (state.data && state.data.errors && state.data.errors.length) return;
    const input = $('filter');
    if (!input) return;
    input.focus();
    input.select();
  }

  async function init() {
    bind();
    await loadStrings();
    applyStrings();
    apply(await call('get_state'));
    if (state.data && state.data.first_run) await runFirstRun();
    focusSearch();
  }

  if (bridge()) {
    init();
  } else {
    window.addEventListener('pywebviewready', init, { once: true });
  }
})();
