#!/usr/bin/env python3
"""
OpenRouter 免费模型监控脚本
监控 https://openrouter.ai/models?q=free 中的免费模型
当有新模型上线时通过 PushPlus 发送通知
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("正在安装 requests 库...")
    os.system("pip3 install --break-system-packages requests")
    import requests

# 配置
DATA_FILE = Path(__file__).parent / "openrouter_models_cache.json"
NOTIFICATION_LOG = Path(__file__).parent / "openrouter_notifications.log"
CHECK_INTERVAL = 3600  # 检查间隔（秒）
OPENROUTER_API = "https://openrouter.ai/api/v1/models"

# PushPlus 配置（从环境变量读取）
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "")
PUSHPLUS_TOPIC = os.getenv("PUSHPLUS_TOPIC", "")


def fetch_free_models():
    """从 OpenRouter API 获取所有免费模型"""
    try:
        response = requests.get(OPENROUTER_API, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        free_models = []
        for model in data.get("data", []):
            pricing = model.get("pricing", {})
            if pricing.get("prompt", "0") == "0" and pricing.get("completion", "0") == "0":
                free_models.append({
                    "id": model.get("id"),
                    "name": model.get("name"),
                    "context_length": model.get("context_length"),
                    "pricing": pricing,
                })
        
        return free_models
    except Exception as e:
        print(f"[错误] 获取模型列表失败：{e}")
        return None


def load_cached_models():
    """加载缓存的模型列表"""
    if not DATA_FILE.exists():
        return None
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("models", [])
    except Exception as e:
        print(f"[警告] 加载缓存失败：{e}")
        return None


def save_models_cache(models):
    """保存模型列表到缓存"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.now().isoformat(),
                "models": models
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[错误] 保存缓存失败：{e}")


def send_pushplus(title, content):
    """发送 PushPlus 通知"""
    if not PUSHPLUS_TOKEN:
        print(f"[提示] 未设置 PUSHPLUS_TOKEN，跳过推送通知")
        print(f"\n{title}\n{content}\n")
        return None
    
    content_html = f"""
<h3>{title}</h3>
<p><strong>检测时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
{content}
<hr>
<p style="font-size:12px;color:#999;">此消息由 OpenRouter Model Monitor 自动推送</p>
"""
    
    url = "https://www.pushplus.plus/send"
    
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content_html,
        "template": "html",
        "channel": "wechat"
    }
    
    if PUSHPLUS_TOPIC:
        data["topic"] = PUSHPLUS_TOPIC
    
    try:
        response = requests.post(url, json=data, timeout=30)
        result = response.json()
        
        if result.get("code") == 200:
            print(f"✓ PushPlus 推送成功")
            return True
        else:
            print(f"✗ PushPlus 推送失败：{result.get('msg', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"✗ PushPlus 请求错误：{e}")
        return False


def log_notification(message):
    """记录通知到日志文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    try:
        with open(NOTIFICATION_LOG, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[错误] 写入日志失败：{e}")
    
    print(log_entry.strip())


def check_new_models():
    """检查是否有新模型"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查免费模型...")
    
    current_models = fetch_free_models()
    if current_models is None:
        print("[错误] 无法获取模型列表，跳过本次检查")
        return
    
    print(f"当前发现 {len(current_models)} 个免费模型")
    
    cached_models = load_cached_models()
    
    if cached_models is None:
        print("[信息] 首次运行，保存初始模型列表")
        save_models_cache(current_models)
        send_pushplus(
            "🤖 OpenRouter 监控已启动",
            f"<p>已记录 <strong>{len(current_models)}</strong> 个免费模型</p><p>后续发现新模型时将及时通知您。</p>"
        )
        return
    
    cached_ids = {model["id"] for model in cached_models}
    current_ids = {model["id"] for model in current_models}
    
    new_model_ids = current_ids - cached_ids
    
    if new_model_ids:
        new_models = [m for m in current_models if m["id"] in new_model_ids]
        
        content_html = ""
        for i, model in enumerate(new_models, 1):
            content_html += f"""
<div style="margin:10px 0;padding:10px;border-left:3px solid #4CAF50;background:#f9f9f9;">
    <strong>{i}. {model['name']}</strong><br>
    <span style="font-size:12px;color:#666;">ID: {model['id']}</span><br>
    <span style="font-size:12px;color:#666;">上下文长度：{model.get('context_length', 'N/A'):,}</span>
</div>
"""
        
        title = f"🎉 发现 {len(new_models)} 个新免费模型"
        send_pushplus(title, content_html)
        log_notification(f"发现 {len(new_models)} 个新模型")
        
        save_models_cache(current_models)
    else:
        print("[信息] 没有新模型")
    
    removed_ids = cached_ids - current_ids
    if removed_ids:
        removed_models = [m for m in cached_models if m["id"] in removed_ids]
        content_html = ""
        for model in removed_models:
            content_html += f"<p>❌ {model.get('name', model['id'])} ({model['id']})</p>"
        
        send_pushplus("⚠️ 模型下架通知", content_html)
        log_notification(f"{len(removed_models)} 个模型下架")
        save_models_cache(current_models)


def main():
    """主函数"""
    print("=" * 60)
    print("OpenRouter 免费模型监控脚本 (PushPlus 通知)")
    print("=" * 60)
    print(f"API 地址：{OPENROUTER_API}")
    print(f"检查间隔：{CHECK_INTERVAL} 秒 ({CHECK_INTERVAL / 3600:.1f} 小时)")
    print(f"PushPlus: {'已配置' if PUSHPLUS_TOKEN else '未配置'}")
    print("=" * 60)
    
    check_new_models()
    
    print(f"\n开始持续监控，按 Ctrl+C 停止...")
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            check_new_models()
    except KeyboardInterrupt:
        print("\n[信息] 监控已停止")


if __name__ == "__main__":
    main()
