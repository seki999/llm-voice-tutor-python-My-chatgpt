# My Local ChatGPT

这是一个可以在本地运行的简易版 My ChatGPT。

## 功能

- 左侧可以定义自己的 My ChatGPT，也就是 system prompt / 角色设定
- 右侧可以输入用户问题
- 支持对话历史
- 支持保存 / 读取 My ChatGPT 设定
- 支持 OpenAI API
- 支持 Local LM Studio，也可以兼容 llama.cpp / Ollama 的 OpenAI-compatible API

## 安装

### 1. 配置本地 Python 环境（推荐使用虚拟环境）

以下步骤以 Windows 11 + PowerShell 为例。

先确认已经安装 Python：

```powershell
python --version
```

如果 `python` 命令不可用，也可以尝试：

```powershell
py --version
```

进入项目目录：

```powershell
cd C:\Users\sekine\Documents\llm-voice-tutor-python-My-chatgpt
```

创建 Python 虚拟环境：

```powershell
python -m venv .venv
```

如果你的电脑使用的是 `py` 命令，则执行：

```powershell
py -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

激活成功后，PowerShell 命令行前面通常会显示：

```text
(.venv)
```

如果 PowerShell 提示 `Activate.ps1` 无法运行、脚本未进行数字签名或执行策略禁止运行，可以只针对当前 PowerShell 窗口临时允许脚本执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

然后重新激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

> `-Scope Process` 只对当前 PowerShell 窗口有效，关闭窗口后设置会自动失效，不会永久修改系统执行策略。

### 2. 安装 Python 依赖

确认命令行前面已经显示 `(.venv)`，然后执行：

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 启动程序

```powershell
python app.py
```

然后浏览器打开：

```text
http://127.0.0.1:7861
```

以后再次启动项目时，不需要重新创建虚拟环境，只需要进入项目目录并激活已有的 `.venv`：

```powershell
cd C:\Users\sekine\Documents\llm-voice-tutor-python-My-chatgpt
.\.venv\Scripts\Activate.ps1
python app.py
```

## 使用 OpenAI API

方法一：PowerShell 设置环境变量

```powershell
$env:OPENAI_API_KEY="sk-你的key"
$env:OPENAI_MODEL="gpt-4o-mini"
python app.py
```

方法二：在 app.py 同目录创建：

```text
openai_api_key.txt
```

把 key 写进去即可。

注意：openai_api_key.txt 不要上传到 GitHub。

## 使用本地 LM Studio

1. 打开 LM Studio
2. 加载一个模型
3. 打开 Local Server
4. 默认地址一般是：

```text
http://localhost:1234/v1/chat/completions
```

5. 启动本 App：

```powershell
python app.py
```

如果模型名不同，可以这样指定：

```powershell
$env:LOCAL_LLM_MODEL="你的模型名"
python app.py
```

## 推荐的 My ChatGPT 设定例子

```text
你是我的私人软件开发教练。

请使用中文回答。
我是一名资深软件工程师，熟悉前端、后端、云计算。
请不要只讲概念，要给出可执行步骤。
如果涉及代码，请给出完整示例。
如果我输入日语，请帮我整理成自然的商务日语。
如果我输入英语，请帮我纠正并解释。
回答要鼓励我继续推进。
```

## 文件说明

- app.py：主程序
- requirements.txt：依赖库
- my_chatgpt_preset.json：点击“保存设定”后自动生成
- chat_history.txt：点击“导出对话”后自动生成
- openai_api_key.txt：可选，本地保存 OpenAI API Key
