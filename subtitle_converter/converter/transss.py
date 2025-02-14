import asyncio
from googletrans import Translator

async def translate_text(translator, text, dest='zh-cn'):
    """异步翻译单个文本行，不再跳过任何格式标记"""
    try:
        translation = await translator.translate(text, dest=dest)
        if translation and translation.text:
            print(f"原文: {text}  ->  译文: {translation.text}")
            return translation.text
        else:
            print(f"翻译 {text} 失败，返回空结果。")
            return f"翻译失败: {text}"
    except Exception as translate_e:
        print(f"翻译 {text} 时发生错误: {translate_e}")
        return f"翻译错误: {text}"

async def translate_srt_string_v4(srt_string, dest='zh-cn'):
    """
    改进后的版本 (v4)，翻译所有文本行，包括 [] 和 <i></i> 内的内容，并保留格式标记。
    移除了对行首字符的判断，现在翻译所有文本行。
    """
    translator = Translator()

    translated_lines = []
    subtitle_entries = srt_string.strip().split('\n\n')

    for entry in subtitle_entries:
        lines = entry.strip().split('\n')
        if len(lines) >= 3:
            try:
                line_number = lines[0]
                timestamp = lines[1]
                text_lines = lines[2:]

                translated_text_lines = []
                for text_line in text_lines:
                    # 移除条件判断，现在直接翻译每一行文本
                    translated_text = await translate_text(translator, text_line, dest)
                    translated_text_lines.append(translated_text)

                translated_entry_lines = [line_number, timestamp] + translated_text_lines
                translated_lines.append('\n'.join(translated_entry_lines))
            except Exception as entry_e:
                print(f"处理字幕条目时出错: {entry}\n错误信息: {entry_e}")
                translated_lines.append(entry)
        else:
            translated_lines.append(entry)

    return '\n\n'.join(translated_lines)


# 示例srt格式字符串 (你的输入)
srt_content = """
1
00:00:21,250 --> 00:00:23,250
[intro to "Let Me Entertain You" by Robbie Williams]

2
00:00:53,625 --> 00:00:55,374
[Robbie Williams VO] Good evening, folks, hmm...

3
00:00:55,375 --> 00:00:56,832
<i>Good evening, you slags.</i>

4
00:00:56,833 --> 00:00:58,332
<i>No, good evening, folks.</i>

5
00:00:58,333 --> 00:01:01,374
<i>So, who is Robbie Williams?</i>

6
00:01:01,375 --> 00:01:03,415
<i>Well, I've been called many things -</i>
"""

async def main():
    translated_srt = await translate_srt_string_v4(srt_content) # 使用 v4 版本
    print("--------------------- 翻译结果 ---------------------")
    print(translated_srt)

if __name__ == "__main__":
    asyncio.run(main())