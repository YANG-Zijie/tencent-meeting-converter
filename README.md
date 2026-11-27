# Tencent Meeting Converter

离线把腾讯会议导出的「逐字稿文本」转换为 SRT 或 WebVTT。保留发言人、开始时间、段落顺序和正文，转换时自动回读校验。需要 Python 3.10+，运行时无第三方依赖。

Convert Tencent Meeting’s exported transcript text to SRT or WebVTT. The tool runs locally and verifies every output cue against the source.

## 安装

```bash
python3 -m pip install git+https://github.com/YANG-Zijie/tencent-meeting-converter.git
```

已下载源码时，在仓库目录运行 `python3 -m pip install .`。

## 使用

```bash
tm-convert meeting.md -o meeting.srt
tm-convert meeting.txt -o meeting.vtt
tm-convert meeting.txt -o meeting.vtt --tail-seconds 8
tm-convert transcripts/*.txt --output-dir subtitles --format vtt
```

批量模式也可混合传入 MD 和 TXT。输出目录会自动创建，批量输出名包含输入扩展名，例如 `meeting.txt.vtt`。若文件已存在，工具拒绝覆盖。批量处理遇到单个文件失败时会继续处理其余文件，并最终返回非零退出码。

## 支持的输入

读取腾讯会议录制页「另存为 → 下载至本地 → 逐字稿文本」导出的 UTF-8 文件。已验证的两种布局如下，示例文字是合成数据。

**TXT**

```text
主持人(00:00:03): 我们开始吧。

参会者(00:00:07): 好的。
```

**MD**

```text
主持人(00:00:03):
我们开始吧。

参会者(00:00:07):
好的。
```

每段之间以空行分隔，支持正文内部的单次换行。其他导出选项（例如省略时间戳）、带元数据的第三方导出和「时间轴文本」可能使用其他布局。遇到无法解析的段落时会报错。

## 时间与发言人

- 逐字稿里的开始时间为整数秒。字幕中的三位毫秒补为 `000`。
- 每段结束时间取下一条严格更晚的开始时间。同秒开始的段落共享区间，依原顺序保留。较长停顿期间字幕会延续显示。
- 最后一组的结束时间为其开始时间加 5 秒，可用 `--tail-seconds` 调整。所有结束时间均为推算值。
- SRT 用 `发言人：正文` 保留姓名，WebVTT 使用原生 `<v 发言人>`。播放器如何显示重叠字幕会有所不同。

转换完成后会显示通过校验的段数、同秒发言组数和推算的最后结束时间。

## 开发与许可

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

本项目采用 [MIT License](LICENSE)，与腾讯会议官方无关联。
