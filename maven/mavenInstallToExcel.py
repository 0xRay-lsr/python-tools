import pandas as pd
import re


def parse_module_results(file_path, out_path):
    # 定义提取模块名的正则表达式
    pattern = r'\[INFO\] ([^\s]+)'
    # 读取日志文件
    with open(file_path, "r") as f:
        lines = f.readlines()
    # 提取模块名
    modules = []
    for line in lines:
        match = re.search(pattern, line)
        if match:
            module_name = match.group(1)
            modules.append(module_name)
    # 创建DataFrame
    df = pd.DataFrame(modules, columns=["Module"])

    # 保存到Excel文件
    df.to_excel(out_path, index=False)


if __name__ == '__main__':
    # 示例读取文件和输出
    file_path = "mavenInstall.txt"
    parse_module_results(file_path, "mavenInstall.xlsx");
