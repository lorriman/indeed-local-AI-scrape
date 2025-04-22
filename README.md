# indeed-local-AI-scrape
Basic demo of scraping Indeed.com with text categorisation and summarisation via local LLM/AI on a Mac Air m2

## rationale

Using online LLMs for multiple simple tasks soon runs through the rate limits (typically 100 a day). So we use our own. Qwen 0.5b was found to be too unintelligent. But 3b has been fine though slow on a Mac Air m2

## Instructions

The project using a running instance of chrome partly to deal with the Captcha. To do this execute this command on Macos (edit the profile name):

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --args --profile-directory="<profilenamehere>"
```

Install Ollama (I used homebrew on my mac), and then get the instance running:

```bash
ollama pull qwen2.5:3b
ollama run qwen2.5:3b
```

To run the script, install the libraries needed:

```bash
pip install playwright pandas requests pyyaml xlsxwriter
```

(Assuming python 3 and pip installed)

Edit config.yaml to make change to the model, ports etc.

## interrupting with ctrl-c

the script can take a long time. It's very slow, as is Indeed.com. If you need to interrupt (ctrl-c) it will still save results to the output excel spreadsheet.

## the spreadsheet

For ease of inspection each cell is 5cmx5cm. 
