import os
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
import re
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


def download_image(url, folder, index):
    """
    下载图片到指定文件夹。
    """
    try:
        ext = os.path.splitext(urlparse(url).path)[-1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            ext = '.jpg'  # Fallback to .jpg if extension is unusual
        filename = f"image_{index}{ext}"
        filepath = os.path.join(folder, filename)

        response = requests.get(url, timeout=10, stream=True)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        # print(f"✅ 图片下载成功: {filename} from {url}") # 可以选择性开启，避免过多输出
        return filename
    except requests.exceptions.RequestException as req_e:
        print(f"⚠️ 图片下载失败 (网络问题): {url}，原因：{req_e}")
        return None
    except Exception as e:
        print(f"⚠️ 图片下载失败 (其他错误): {url}，原因：{e}")
        return None


def clean_filename(title):
    """
    清理标题，使其适合作为文件名。
    移除特殊字符，替换空格为下划线，限制长度。
    """
    cleaned_title = re.sub(r'[^\w\s-]', '', title)
    cleaned_title = re.sub(r'\s+', '_', cleaned_title).strip()
    if len(cleaned_title) > 100:
        cleaned_title = cleaned_title[:100]
    return cleaned_title if cleaned_title else "untitled_article"  # 防止空标题导致文件名问题


def fetch_wechat_article(url):
    """
    获取微信公众号文章内容，并保存为Markdown文件。
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 更真实的User-Agent，模拟Chrome浏览器在Windows环境
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--log-level=3")  # 减少webdriver的日志输出

    service = Service(ChromeDriverManager().install())
    driver = None

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)

        print(f"🚀 正在加载微信文章: {url}")
        driver.get(url)

        # 使用WebDriverWait等待页面主要元素加载
        try:
            # 等待文章标题或文章正文区域出现
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "activity-name")) or
                EC.presence_of_element_located((By.CLASS_NAME, "rich_media_title")) or
                EC.presence_of_element_located((By.ID, "js_content"))
            )
            print("页面主要元素已加载。")
        except Exception as e:
            print(f"⚠️ 等待主要元素超时或失败: {e}")
            # 即使等待失败也尝试继续，可能页面部分加载了

        # 获取页面HTML
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # --- 获取文章主标题 ---
        title = "未命名文章"

        # 优先级1: 通过ID 'activity-name'
        title_tag = soup.find("h1", {"id": "activity-name"})
        if title_tag:
            title = title_tag.get_text(strip=True)
            print(f"✅ 成功获取主标题 (通过ID): '{title}'")
        else:
            # 优先级2: 通过class 'rich_media_title'
            title_tag = soup.find("h2", {"class": "rich_media_title"})
            if title_tag:
                title = title_tag.get_text(strip=True)
                print(f"✅ 成功获取主标题 (通过Class): '{title}'")
            else:
                # 优先级3: 通过meta og:title (通常是页面的标题，不总是文章主标题，但作为备用)
                meta_title_tag = soup.find("meta", property="og:title")
                if meta_title_tag and meta_title_tag.get("content"):
                    title = meta_title_tag.get("content").strip()
                    print(f"✅ 成功获取主标题 (通过Meta OG Title): '{title}'")
                else:
                    print("⚠️ 未能通过常见方式获取到文章主标题，使用默认标题。")

        # 清理标题，用于文件名
        cleaned_title = clean_filename(title)

        content_div = soup.find("div", {"id": "js_content"})
        if not content_div:
            raise Exception("❌ 无法找到文章正文内容 (#js_content)，请检查URL或页面结构。")

        # 创建目录
        folder_name = "wechat_articles"
        article_folder = os.path.join(folder_name, cleaned_title)
        img_folder = os.path.join(article_folder, "images")
        os.makedirs(img_folder, exist_ok=True)
        print(f"📁 已创建文章目录: {article_folder}")

        # 构建 Markdown 内容
        md_lines = [f"# {title}\n\n"]  # 主标题作为Markdown的H1

        img_count = 0

        # 遍历正文内容，处理段落、小标题和图片
        # 重要的改进：遍历js_content的直接子元素，并针对不同标签进行处理
        for element in content_div.children:
            if not element.name:  # 忽略NavigableString类型的文本节点
                continue

            # 处理小标题 (h1-h6)
            if re.match(r'^h[1-6]$', element.name):
                # 微信文章中的h标签不一定是真的H标签，有时是div+span模拟
                # 但如果确实是h标签，我们按其级别转换为Markdown
                level = int(element.name[1])
                md_lines.append(f"{'#' * level} {element.get_text(strip=True)}\n")
            elif element.name == 'section' or element.name == 'p' or element.name == 'div':
                # 处理段落文本
                text = element.get_text(strip=True)
                if text:
                    md_lines.append(text + "\n")

                # 再次尝试在section/p/div内部查找可能的“小标题”样式
                # 微信文章常用 style="font-size: xxx; font-weight: bold;" 或 span
                # 这是一个启发式方法，可能不完美
                for inner_tag in element.find_all(['strong', 'span', 'b', 'p']):
                    style = inner_tag.get('style', '')
                    # 检查是否有字体大小较大且加粗的样式
                    if ("font-size" in style and "bold" in style) or \
                            ("font-size" in style and "weight:700" in style) or \
                            ("font-weight:bold" in style) or \
                            ("font-weight:700" in style):
                        inner_text = inner_tag.get_text(strip=True)
                        if inner_text and len(inner_text) > 3 and not inner_text.endswith("。"):  # 避免捕获普通加粗句子
                            # 估算小标题级别，这里简单统一为二级标题，或根据字体大小进一步判断
                            # 如果有多个不同大小的，可以更复杂地分析
                            md_lines.append(f"## {inner_text}\n")
                            # 移除已处理的小标题文本，避免重复输出为普通段落
                            # 注意：这会修改soup对象，可能影响后续处理
                            # 更好的做法是在append之后标记一下，或跳过
                            inner_tag.extract()  # 从soup中移除，避免作为普通文本再次添加

            # 查找所有图片（包括在各种嵌套标签内的）
            for img in element.find_all("img"):
                img_url = img.get("data-src") or img.get("src")
                # 过滤掉一些可能是背景图或很小的图标，也可以检查 src 是否是 data:image
                if img_url and img_url.startswith("http") and "wx_fmt" in img_url:  # 微信图片的特点通常有wx_fmt
                    img_count += 1
                    local_filename = download_image(img_url, img_folder, img_count)
                    if local_filename:
                        # 确保 alt 属性不是 None
                        alt_text = img.get('alt', '').strip()
                        if not alt_text:  # 如果alt为空，尝试从data-alt获取
                            alt_text = img.get('data-alt', '').strip()

                        md_lines.append(f"![{alt_text}](images/{local_filename})\n")

            # 处理视频（如果需要）
            for video_tag in element.find_all("video"):
                video_src = video_tag.get("src") or video_tag.get("data-src")
                if video_src:
                    md_lines.append(f"> **[视频链接]** {video_src}\n")

            # 处理链接（如果需要）
            for a_tag in element.find_all("a"):
                link_href = a_tag.get("href")
                link_text = a_tag.get_text(strip=True)
                if link_href and link_text:
                    md_lines.append(f"[{link_text}]({link_href})\n")

        # 写入 Markdown 文件
        md_filename = os.path.join(article_folder, f"{cleaned_title}.md")
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        print(f"✅ 抓取完成！文章标题: '{title}'")
        print(f"   共下载 {img_count} 张图片到 '{img_folder}'")
        print(f"   Markdown 文件已保存到 '{md_filename}'")

    except Exception as e:
        print(f"❌ 抓取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()  # 打印完整的错误栈信息，方便调试
    finally:
        if driver:
            driver.quit()
            print("🌐 Chrome 浏览器已关闭。")


if __name__ == "__main__":
    # 请替换为你要抓取的微信文章URL
    wechat_url = "https://mp.weixin.qq.com/s/jy-tqjeV8IJAH9hTd4Oyjw"  # 一个示例文章
    # wechat_url = "https://mp.weixin.qq.com/s/z926V-r1FjXk0F5v_5g2Cg" # 另一个示例，可能有不同的结构
    # wechat_url = "https://mp.weixin.qq.com/s/YourActualArticleURLHere"
    fetch_wechat_article(wechat_url)
