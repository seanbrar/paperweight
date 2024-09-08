import tiktoken
import yaml


def load_config():
    with open('config.yaml', 'r') as config_file:
        return yaml.safe_load(config_file)

def count_tokens(text):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(text, allowed_special={'<|endoftext|>'}))
