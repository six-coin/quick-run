import urllib.parse

import vlc

from libs import log


def text_to_speech(search_text):
    def is_english_only(check_text):
        try:
            check_text.encode('ascii')
            return True
        except UnicodeEncodeError:
            return False

    try:
        is_eng = is_english_only(search_text)
        # 编码文本到 URL 格式
        encoded_text = urllib.parse.quote(search_text)
        # 美式发音 URL
        if is_eng:
            url = f"https://fanyi.baidu.com/gettts?lan=en&text={encoded_text}&spd=3&source=web"
        else:
            url = f"https://fanyi.baidu.com/gettts?lan=zh&text={encoded_text}&spd=3&source=web"
        # 创建播放器
        player = vlc.MediaPlayer(url)
        player.play()
        player.set_time(0)
        if is_eng:
            log.write(f"播放英语发音：{search_text}", 3)
        else:
            log.write(f"播放中文发音：{search_text}", 3)
    except Exception as e:
        log.write(f"播放发音 {search_text} 失败：{e}", 3)
        log.write(f"解决方法参考：安装软件 VLC Media Player", 3)
