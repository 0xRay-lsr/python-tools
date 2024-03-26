import os
import glob
import fileinput
import re

# java文件目录
replace_java_file_folder = ["src/main/java", "src/test/java"]
# 资源文件目录
replace_java_resource_folder = ["src/main/resources", "src/test/resources"]
# 指定旧的包名和新的包名
old_package = "cn.xxx"
new_package = "com.xxx.xxx"
# 构建包名的正则表达式
package_pattern = r'\b' + re.escape(old_package) + r'\b'
# 待删除的文件路径过滤
delete_file_path = "cn/sunline"
# groupId 规则
group_id_rules = [
    (re.escape(fr"<groupId>{old_package}"), fr"<groupId>{new_package}")
    # 添加更多规则...
]


def replace_package_and_path(root_directory):
    # 遍历根目录下的所有子模块
    for item in glob.glob(os.path.join(root_directory, "**/pom.xml"), recursive=True):
        # 替换 pom.xml 中的 <groupId>
        with fileinput.FileInput(item, inplace=True) as file:
            for line in file:
                new_line = replace_group_id(line, group_id_rules)
                print(new_line, end='')

        module_directory = os.path.dirname(item)
        for i in range(len(replace_java_file_folder)):
            current_java_file_folder = replace_java_file_folder[i]
            current_java_resource_folder = replace_java_resource_folder[i];
            java_file_folder_package_directory = os.path.join(module_directory, current_java_file_folder)
            java_resource_package_directory = os.path.join(module_directory, current_java_resource_folder)
            if os.path.isdir(java_file_folder_package_directory):
                # 遍历子模块下的所有 Java 文件
                for file_path in glob.glob(os.path.join(java_file_folder_package_directory, "**/*.java"),
                                           recursive=True):
                    # 读取文件内容
                    with open(file_path, 'r', encoding='ISO-8859-1') as file:
                        file_content = file.read()

                    # 替换 package
                    # new_content = # 替换包名
                    new_content = re.sub(package_pattern, new_package, file_content)

                    # 构建正则表达式模式
                    class_pattern = fr"(?<={re.escape(current_java_file_folder + '/')})({re.escape(old_package.replace('.', '/'))})(?=/)"

                    # 使用变量替换文件路径
                    new_file_path = re.sub(class_pattern, new_package.replace('.', '/'), file_path)

                    # 确保新文件路径的目录存在
                    os.makedirs(os.path.dirname(new_file_path), exist_ok=True)

                    # 将替换后的内容写入新文件路径
                    with open(new_file_path, 'w', encoding='ISO-8859-1') as file:
                        file.write(new_content)
                    # 删除替换前的文件
                    if delete_file_path in file_path:
                        # 删除原文件
                        os.remove(file_path)

                # 删除原始文件夹 替换后原始文件夹为空文件夹，但是存在，手动删除
                delete_empty_folders(java_file_folder_package_directory)
                # 替换 Spring 配置文件中的内容
                spring_factories_path = os.path.join(module_directory, "src/main/resources/META-INF/spring.factories")
                if os.path.isfile(spring_factories_path):
                    with fileinput.FileInput(spring_factories_path, inplace=True) as file:
                        for line in file:
                            new_line = re.sub(fr"(?<=^)(\s*){re.escape(old_package)}", r"\1" + new_package, line)
                            print(new_line, end='')
                # 构建正则表达式模式
                if os.path.isdir(java_resource_package_directory):
                    # 遍历子模块下的所有资源文件
                    for file_path in glob.glob(os.path.join(java_resource_package_directory, "**/*"), recursive=True):
                        # 只处理文件，不处理文件夹
                        if file_path.endswith(('.properties', '.xml', '.ftl')):
                            # 输出文件路径
                            print("处理文件:", file_path)

                            # 读取文件内容
                            with open(file_path, 'r', encoding='ISO-8859-1') as file:
                                file_content = file.read()

                            # 替换文件内容
                            new_content = re.sub(
                                fr"(?<=^)(.*{re.escape(old_package)}.*)",
                                lambda match: match.group().replace(old_package, new_package),
                                file_content,
                                flags=re.MULTILINE
                            )

                            # 将替换后的内容写入文件
                            with open(file_path, 'w', encoding='ISO-8859-1') as file:
                                file.write(new_content)


def replace_group_id(line, rules):
    updated_line = line
    for old_group_id, new_group_id in rules:
        updated_line = re.sub(old_group_id, new_group_id, updated_line)
    return updated_line


def delete_empty_folders(folder_path):
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for folder in dirs:
            folder_path = os.path.join(root, folder)
            if not os.listdir(folder_path):
                os.rmdir(folder_path)


def replace_all():
    # 指定根目录
    root_directory = "/Users/lsr/Desktop/code/xxx"
    # 替换根目录下的所有子模块的包名和文件路径
    replace_package_and_path(root_directory)


# 一件修改maven 工程的包名，groupid，resources下的文件，规则匹配
if __name__ == "__main__":
    replace_all()
