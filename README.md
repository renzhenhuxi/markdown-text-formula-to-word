# markdown-formula-to-word
将AI生成的Markdown/LaTeX数学公式转换为Word原生可识别的MathML公式，适合写实验报告、课程作业。支持文字和公式混合内容导入，导出稳定，可直接粘贴进Word。

## 📂 版本说明
三个版本都可以正常使用，只是界面和功能侧重点不同：
- `main/markdown3.py`：✅【最新版】GUI界面，样式更美观，支持自定义壁纸
<img width="1146" height="721" alt="Screenshot 2026-11-16 234418" src="https://github.com/user-attachments/assets/4322a3fe-7bc1-4ea9-beaa-3bb876fa9336" />

- `simple_version/markdown2.py`：第二版，GUI版本，偏向简洁实用
- `simple_version/markdown1.py`：初代基础版本，无GUI，极简实用

> 前两个版本已经打包为本地exe桌面程序；编译后的exe不放在源码目录，后续会放在 GitHub Releases 分发。

## ✨ 功能
- 解析大模型输出的Markdown格式LaTeX公式块
- 非常便捷，复制后点击一键粘贴即可使用
- 也支持文档转换
- 支持**文字+公式混合内容**导入
- 转换为标准MathML，粘贴到Word自动识别为原生公式
- 输出稳定，适配实验报告、课程作业场景
## 使用方法
- 直接复制文字或者把带markedown或者latex的文件丢给它就行了
- 第3版和第二版会有一个预览界面
- 第一版直接在word内预览
- 觉得合适就可以直接保存，他就会生成一个新的word文档
- 主包测试的不多，不过感觉功能挺稳定的
- 推荐使用2和3版
- 3版用ai优化下界面，非常帅气，虽然没啥用
- 3版那个透明度是可以调的，还有竖着横着两种模式

## 🧩 运行环境
- Python：3.8 – 3.12（推荐 3.10 / 3.11）
- tkinter（Python自带，无需额外安装）

## 📦 依赖安装
```bash
pip install -r requirements.txt




