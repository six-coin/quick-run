(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  const FIELD_INPUTS = {
    display: 'f-display',
    keywords: 'f-keywords',
    path: 'f-path',
    dir: 'f-dir',
    url: 'f-url',
    command: 'f-command',
  };

  const state = {
    data: null,
    filter: '',
    collapsed: new Set(),
    dragging: null,
    bound: false,
    lastSelection: '',
    suppressClickUntil: 0,
  };

  const pending = new Map();
  let toastTimer = null;
  let confirmAction = null;

  // -- bridge -------------------------------------------------------------
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
      toast('操作失败：' + error, false);
      return null;
    }
  }

  // -- deferred edits -----------------------------------------------------
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

  // -- helpers ------------------------------------------------------------
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
    return parts.length ? parts.join(' · ') : '无匹配字串';
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

  function chevron() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'chevron');
    svg.setAttribute('viewBox', '0 0 16 16');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M4 6l4 4 4-4');
    svg.appendChild(path);
    return svg;
  }

  // -- rendering ----------------------------------------------------------
  function apply(data) {
    if (!data) return;
    state.data = data;

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

  function renderOptions(data) {
    const pills = $('type-pills');
    if (pills.childElementCount === 0) {
      data.types.forEach(function (item) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'pill';
        button.dataset.type = item.value;
        button.textContent = item.label;
        button.addEventListener('click', function () {
          changeType(item.value);
        });
        pills.appendChild(button);
      });
    }

    const functionSelect = $('f-function');
    const menu = functionSelect.querySelector('.select-menu');
    if (menu.childElementCount === 0) {
      data.debug_functions.forEach(function (item) {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'select-option';
        option.dataset.value = item.value;
        option.textContent = item.label;
        option.addEventListener('click', function (event) {
          event.stopPropagation();
          chooseFunction(item.value);
        });
        menu.appendChild(option);
      });
    }
  }

  function renderGroups() {
    const list = $('list');
    list.innerHTML = '';
    if (!state.data) return;

    const entries = visibleGroups();
    if (!entries.length) {
      const empty = document.createElement('div');
      empty.className = 'list-empty';
      empty.textContent = state.filter ? '没有匹配的操作' : '还没有任何操作';
      list.appendChild(empty);
      return;
    }

    const sel = selection();
    entries.forEach(function (entry) {
      const group = entry.group;
      const section = document.createElement('section');
      section.className = 'group';
      section.dataset.group = String(group.index);
      if (!group.enabled) section.classList.add('disabled');
      if (state.collapsed.has(group.name)) section.classList.add('collapsed');

      const head = document.createElement('div');
      head.className = 'group-head';
      head.dataset.group = String(group.index);
      head.draggable = !state.filter;
      if (sel.kind === 'group' && sel.group === group.index) head.classList.add('active');

      head.appendChild(chevron());

      const name = document.createElement('span');
      name.className = 'group-name';
      name.textContent = group.name;
      head.appendChild(name);

      const count = document.createElement('span');
      count.className = 'group-count';
      count.textContent = String(group.count);
      head.appendChild(count);

      const toggle = document.createElement('label');
      toggle.className = 'switch mini';
      toggle.title = group.enabled ? '关闭该分组' : '启用该分组';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = group.enabled;
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
        if (event.target.closest('.switch')) return;
        if (event.target.closest('.chevron')) {
          toggleCollapse(group.name, section);
          return;
        }
        call('select_group', group.index).then(apply);
      });

      section.appendChild(head);

      const ops = document.createElement('ul');
      ops.className = 'group-ops';
      ops.dataset.group = String(group.index);

      entry.operations.forEach(function (operation) {
        ops.appendChild(renderOperation(operation, sel));
      });

      section.appendChild(ops);
      list.appendChild(section);
    });
  }

  function renderOperation(operation, sel) {
    const item = document.createElement('li');
    item.className = 'item';
    item.dataset.group = String(operation.group);
    item.dataset.index = String(operation.index);
    item.draggable = !state.filter;
    if (sel.kind === 'operation' && sel.group === operation.group && sel.index === operation.index) {
      item.classList.add('selected');
    }

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
    $('group-sub').textContent =
      group.count + ' 条操作' + (group.enabled ? '' : ' · 已关闭');
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
    setFunctionValue(args.function || 'restart');

    $('btn-up').disabled = operation.index === 0;
    $('btn-down').disabled = operation.index === currentGroup().operations.length - 1;

    updateDepthVisibility();
  }

  function renderDirty(dirty) {
    $('dirty-badge').classList.toggle('hidden', !dirty);
    document.title = (dirty ? '• ' : '') + 'Fast Run 操作管理器';
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
      text = shown + ' / ' + total + ' 项';
    } else {
      text = total + ' 项 · ' + groups + ' 组';
    }
    if (enabled !== total) text += ' · ' + enabled + ' 启用';
    $('count-label').textContent = text;
  }

  function updateDepthVisibility() {
    const allowed = $('f-allow-explore').checked;
    $('row-depth').classList.toggle('hidden', !allowed);
  }

  function updateLabel(group, index, text) {
    const label = text || '未命名操作';
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

  function showModal(id) {
    $(id).classList.remove('hidden');
  }

  function hideModal(id) {
    $(id).classList.add('hidden');
  }

  function askConfirm(title, text, action) {
    $('confirm-title').textContent = title;
    $('confirm-text').textContent = text;
    confirmAction = action;
    showModal('modal-confirm');
  }

  function toggleCollapse(name, section) {
    if (state.collapsed.has(name)) {
      state.collapsed.delete(name);
      section.classList.remove('collapsed');
    } else {
      state.collapsed.add(name);
      section.classList.add('collapsed');
    }
  }

  // -- actions ------------------------------------------------------------
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

    const data = await call('add_operation', group === undefined ? null : group);
    if (!data) return;

    const target = data.groups[data.selection.group];
    if (target) state.collapsed.delete(target.name);
    apply(data);

    const item = document.querySelector('.item.selected');
    if (item) {
      item.classList.add('flash');
      item.scrollIntoView({ block: 'nearest' });
    }
  }

  function setFunctionValue(value) {
    const select = $('f-function');
    const option = select.querySelector('.select-option[data-value="' + value + '"]');
    select.dataset.value = value;
    select.querySelector('.select-value').textContent = option ? option.textContent : value;
    select.querySelectorAll('.select-option').forEach(function (item) {
      item.classList.toggle('active', item.dataset.value === value);
    });
  }

  async function chooseFunction(value) {
    const select = $('f-function');
    select.classList.remove('open');
    const operation = currentOperation();
    if (!operation) return;
    setFunctionValue(value);
    await call('set_argument', operation.group, operation.index, 'function', value);
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
      count.textContent = group.count + ' 条';

      button.appendChild(name);
      button.appendChild(count);
      button.addEventListener('click', async function () {
        hideModal('modal-group');
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

    showModal('modal-group');
  }

  // -- bindings -----------------------------------------------------------
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
      const head = document.querySelector('.group-head[data-group="' + group.index + '"] .group-name');
      if (head) head.textContent = value || '未命名分组';
      markDirty();
    });

    $('f-group-enabled').addEventListener('change', function (event) {
      const group = currentGroup();
      if (!group || selection().kind !== 'group') return;
      call('set_group_enabled', group.index, event.target.checked).then(apply);
    });

    document.querySelectorAll('[data-arg]').forEach(function (input) {
      const key = input.dataset.arg;
      const eventName = input.tagName === 'SELECT' || input.type === 'checkbox' ? 'change' : 'input';
      input.addEventListener(eventName, function () {
        const operation = currentOperation();
        if (!operation) return;
        let value;
        if (input.type === 'checkbox') value = input.checked;
        else value = input.value;
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

    const functionSelect = $('f-function');
    functionSelect.addEventListener('click', function (event) {
      event.stopPropagation();
      functionSelect.classList.toggle('open');
    });
    functionSelect.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        functionSelect.classList.toggle('open');
      } else if (event.key === 'Escape') {
        functionSelect.classList.remove('open');
      }
    });
    document.addEventListener('click', function () {
      functionSelect.classList.remove('open');
    });

    $('btn-move-group').addEventListener('click', openGroupPicker);

    $('btn-add').addEventListener('click', function () {
      addOperation();
    });
    $('btn-add-empty').addEventListener('click', function () {
      addOperation();
    });
    $('btn-add-group').addEventListener('click', async function () {
      await flushPending();
      apply(await call('add_group'));
    });
    $('btn-group-add-op').addEventListener('click', function () {
      const group = currentGroup();
      addOperation(group ? group.index : null);
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
        '删除操作',
        '确定删除「' + operation.label + '」吗？该操作会从配置中移除。',
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
        '删除分组',
        '确定删除分组「' + group.name + '」吗？组内 ' + group.count + ' 条操作会一起被删除。',
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
      hideModal('modal-confirm');
    });

    $('btn-save').addEventListener('click', function () {
      save();
    });

    $('btn-help').addEventListener('click', async function () {
      const html = await call('help_html');
      if (html) $('help-body').innerHTML = html;
      showModal('modal-help');
    });

    document.querySelectorAll('[data-close]').forEach(function (button) {
      button.addEventListener('click', function () {
        hideModal(button.dataset.close);
      });
    });

    document.addEventListener('keydown', function (event) {
      const modifier = event.ctrlKey || event.metaKey;
      if (modifier && event.key.toLowerCase() === 's') {
        event.preventDefault();
        save();
      } else if (modifier && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        $('filter').focus();
        $('filter').select();
      } else if (event.key === 'Escape') {
        const openModal = document.querySelector('.modal:not(.hidden)');
        if (openModal) {
          confirmAction = null;
          openModal.classList.add('hidden');
        } else if (state.filter) {
          $('filter-clear').click();
        }
      }
    });

    const list = $('list');

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
        if (event.target.closest('.switch')) {
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
        if (toGroup === dragging.group && (toIndex === dragging.index || toIndex === dragging.index + 1)) {
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

  // -- bootstrap ----------------------------------------------------------
  async function init() {
    bind();
    apply(await call('get_state'));
  }

  if (bridge()) {
    init();
  } else {
    window.addEventListener('pywebviewready', init, { once: true });
  }
})();
