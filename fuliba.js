/**
 * 福利吧 (Fuliba) 自动签到脚本 - 优化增强版
 * 
 * 功能：
 * 1. 自动遍历可用域名
 * 2. 增强型数据提取 (支持已签/未签状态)
 * 3. 错误自动重试
 * 4. 详细的推送报告 (TG + PushPlus)
 */

const axios = require('axios');

// ================= 配置区域 =================
const CONFIG = {
    cookies: (process.env.FULI_COOKIE || '').split('@').filter(Boolean),
    tgBotToken: process.env.TG_BOT_TOKEN,
    tgChatId: process.env.TG_CHAT_ID,
    pushPlusToken: process.env.PUSHPLUS_TOKEN,
    domains: [
        "https://www.wnflb2025.com",
        "https://www.wnflb2024.com",
        "https://fuliba2025.bar",
        "https://www.wnflb00.com",
        "https://www.wnflb99.com"
    ],
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
};

// ================= 推送模块 =================
async function notify(title, content) {
    console.log(`\n--- [通知推送] --- \n${title}\n${content}`);
    
    const tasks = [];
    
    // Telegram
    if (CONFIG.tgBotToken && CONFIG.tgChatId) {
        tasks.push(
            axios.post(`https://api.telegram.org/bot${CONFIG.tgBotToken}/sendMessage`, {
                chat_id: CONFIG.tgChatId,
                text: `<b>${title}</b>\n\n${content}`,
                parse_mode: "HTML",
                disable_web_page_preview: true
            }).catch(e => console.error(`TG 推送失败: ${e.message}`))
        );
    }

    // PushPlus
    if (CONFIG.pushPlusToken) {
        tasks.push(
            axios.post('http://www.pushplus.plus/send', {
                token: CONFIG.pushPlusToken,
                title: title,
                content: content.replace(/\n/g, '<br>'),
                template: 'html'
            }).catch(e => console.error(`PushPlus 推送失败: ${e.message}`))
        );
    }

    await Promise.all(tasks);
}

// ================= 逻辑模块 =================

class FulibaSigner {
    constructor(cookie, index) {
        this.cookie = cookie;
        this.index = index;
        this.baseUrl = '';
        this.http = null;
    }

    // 自动寻找有效域名
    async findActiveDomain() {
        for (const domain of CONFIG.domains) {
            try {
                const res = await axios.get(domain, { timeout: 5000, validateStatus: () => true });
                if (res.status < 500) {
                    this.baseUrl = domain;
                    this.http = axios.create({
                        baseURL: domain,
                        timeout: 10000,
                        headers: {
                            'Cookie': this.cookie,
                            'User-Agent': CONFIG.userAgent,
                            'Referer': domain + '/'
                        }
                    });
                    return true;
                }
            } catch (e) {
                continue;
            }
        }
        return false;
    }

    // 提取用户信息及状态
    parseInfo(html) {
        const regexGet = (regex) => (html.match(regex) || [])[1] || '未知';
        
        // 登录校验
        if (html.includes('请先登录') || !html.includes('formhash')) {
            return null;
        }

        return {
            formhash: regexGet(/name="formhash" value="(\w+)"/) || regexGet(/formhash=(\w+)/),
            username: regexGet(/id="username">([^<]+)</) || regexGet(/class="xw1">([^<]+)</) || '匿名',
            todayRank: regexGet(/今日签到排名\D*(\d+)/) || regexGet(/第\D*(\d+)\D*名/),
            contiDays: regexGet(/已连续签到\D*(\d+)/) || '0',
            totalDays: regexGet(/累计签到\D*(\d+)/) || '0',
            totalRank: regexGet(/个人排名\D*(\d+)/) || 'N/A'
        };
    }

    async run() {
        try {
            if (!await this.findActiveDomain()) {
                return `账号${this.index}: ❌ 无法连接到任何有效域名`;
            }

            // 1. 获取 Formhash
            let { data: html } = await this.http.get('/plugin.php?id=fx_checkin:list');
            let info = this.parseInfo(html);

            if (!info) {
                return `账号${this.index}: ❌ Cookie 已过期或失效`;
            }

            // 2. 执行签到
            const checkinRes = await this.http.get(`/plugin.php?id=fx_checkin:checkin&formhash=${info.formhash}&inajax=1`);
            const isAlreadyDone = checkinRes.data.includes('已经签到') || checkinRes.data.includes('已经全部签到');

            // 3. 再次获取最新数据
            const { data: finalHtml } = await this.http.get('/plugin.php?id=fx_checkin:list');
            const after = this.parseInfo(finalHtml);

            const statusEmoji = isAlreadyDone ? '🔁' : '✅';
            const statusText = isAlreadyDone ? '今日已签到' : '签到成功';

            return `${statusEmoji} <b>账号: ${after.username}</b> (${statusText})\n` +
                   `🏆 今日排名：第 <b>${after.todayRank}</b> 名\n` +
                   `🔥 连续签到：<b>${after.contiDays}</b> 天\n` +
                   `📊 累计签到：<b>${after.totalDays}</b> 天\n` +
                   `🌐 站点：${this.baseUrl}`;

        } catch (e) {
            return `账号${this.index}: ❌ 运行异常 (${e.message})`;
        }
    }
}

// ================= 主程序 =================
(async () => {
    const { cookies } = CONFIG;
    
    if (cookies.length === 0) {
        await notify('福利吧签到系统', '❌ 未检测到有效的 FULI_COOKIE');
        return;
    }

    console.log(`🚀 开始执行福利吧签到，共 ${cookies.length} 个账号`);
    const results = [];

    for (let i = 0; i < cookies.length; i++) {
        const signer = new FulibaSigner(cookies[i], i + 1);
        const result = await signer.run();
        results.push(result);
        
        console.log(`[账号 ${i + 1}] 执行完毕`);

        // 账号间随机延迟 3-8s
        if (i < cookies.length - 1) {
            const delay = Math.floor(Math.random() * 5000) + 3000;
            await new Promise(r => setTimeout(r, delay));
        }
    }

    const summary = results.join('\n\n' + '-'.repeat(30) + '\n\n');
    const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
    
    await notify(`🔔 福利吧签到报告 (${now})`, summary);
})();
