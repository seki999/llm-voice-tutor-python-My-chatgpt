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

```powershell
cd C:\Users\sekine\Documents\llm-voice-tutor-python-My-chatgpt
pip install -r requirements.txt
python app.py
```

然后浏览器打开：

```text
http://127.0.0.1:7860
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
