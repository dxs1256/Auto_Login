const axios = require('axios');
const { chromium } = require('playwright');

const token = process.env.TG_BOT_TOKEN;
const chatId = process.env.TG_CHAT_ID;
const pushplusToken = process.env.PUSHPLUS_TOKEN; // 获取 PushPlus Token
const accounts = process.env.NETLIB_ACCOUNTS;

if (!accounts) {
  console.log('❌ 未配置账号');
  process.exit(1);
}

// 解析多个账号，支持逗号或分号分隔
const accountList = accounts.split(/[,;]/).map(account => {
  const [user, pass] = account.split(":").map(s => s.trim());
  return { user, pass };
}).filter(acc => acc.user && acc.pass);

if (accountList.length === 0) {
  console.log('❌ 账号格式错误，应为 username1:password1,username2:password2');
  process.exit(1);
}

// 获取格式化的时间字符串 (HKT)
function getHkTimeStr() {
  const now = new Date();
  const hkTime = new Date(now.getTime() + (8 * 60 * 60 * 1000));
  return hkTime.toISOString().replace('T', ' ').substr(0, 19) + " HKT";
}

async function sendTelegram(message) {
  if (!token || !chatId) {
    console.log('⚠️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 通知');
    return;
  }

  const timeStr = getHkTimeStr();
  const fullMessage = `🎉 Netlib 登录通知\n\n登录时间：${timeStr}\n\n${message}`;

  try {
    await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, {
      chat_id: chatId,
      text: fullMessage
    }, { timeout: 10000 });
    console.log('✅ Telegram 通知发送成功');
  } catch (e) {
    console.log('⚠️ Telegram 发送失败:', e.message);
  }
}

async function sendPushPlus(message) {
  if (!pushplusToken) {
    console.log('⚠️ 未配置 PUSHPLUS_TOKEN，跳过 PushPlus 通知');
    return;
  }

  const timeStr = getHkTimeStr();
  // 简单处理一下换行，使其在 Markdown 中显示更好
  const fullMessage = `#### Netlib 登录通知\n\n**时间**：${timeStr}\n\n${message}`;

  try {
    const response = await axios.post('http://www.pushplus.plus/send', {
      token: pushplusToken,
      title: 'Netlib 登录通知',
      content: fullMessage,
      template: 'markdown',
      channel: 'wechat'
    }, { timeout: 10000 });

    if (response.data && response.data.code === 200) {
      console.log('✅ PushPlus 通知发送成功');
    } else {
      console.log(`❌ PushPlus 发送失败: ${response.data.msg}`);
    }
  } catch (e) {
    console.log('⚠️ PushPlus 请求异常:', e.message);
  }
}

async function loginWithAccount(user, pass) {
  console.log(`\n🚀 开始登录账号: ${user}`);
  
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  let page;
  let result = { user, success: false, message: '' };
  
  try {
    page = await browser.newPage();
    page.setDefaultTimeout(30000);
    
    console.log(`📱 ${user} - 正在访问网站...`);
    await page.goto('https://www.netlib.re/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    
    console.log(`🔑 ${user} - 点击登录按钮...`);
    // 尝试不同的选择器来点击登录，增加健壮性
    try {
        await page.click('a[href*="login"]', { timeout: 5000 });
    } catch {
        await page.click('text=Login', { timeout: 5000 });
    }
    
    await page.waitForTimeout(2000);
    
    console.log(`📝 ${user} - 填写用户名...`);
    await page.fill('input[name="username"], input[type="text"]', user);
    await page.waitForTimeout(1000);
    
    console.log(`🔒 ${user} - 填写密码...`);
    await page.fill('input[name="password"], input[type="password"]', pass);
    await page.waitForTimeout(1000);
    
    console.log(`📤 ${user} - 提交登录...`);
    await page.click('button:has-text("Validate"), input[type="submit"]');
    
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000);
    
    // 检查登录是否成功
    const pageContent = await page.content();
    
    if (pageContent.includes('exclusive owner') || pageContent.includes(user)) {
      console.log(`✅ ${user} - 登录成功`);
      result.success = true;
      result.message = `✅ ${user}: 登录成功`;
    } else {
      console.log(`❌ ${user} - 登录失败`);
      result.message = `❌ ${user}: 登录失败 (未检测到登录后标识)`;
    }
    
  } catch (e) {
    console.log(`❌ ${user} - 登录异常: ${e.message}`);
    result.message = `❌ ${user}: 登录异常 - ${e.message}`;
  } finally {
    if (page) await page.close();
    await browser.close();
  }
  
  return result;
}

async function main() {
  console.log(`🔍 发现 ${accountList.length} 个账号需要登录`);
  
  const results = [];
  
  for (let i = 0; i < accountList.length; i++) {
    const { user, pass } = accountList[i];
    console.log(`\n📋 处理第 ${i + 1}/${accountList.length} 个账号: ${user}`);
    
    const result = await loginWithAccount(user, pass);
    results.push(result);
    
    // 如果不是最后一个账号，等待一下再处理下一个
    if (i < accountList.length - 1) {
      console.log('⏳ 等待3秒后处理下一个账号...');
      await new Promise(resolve => setTimeout(resolve, 3000));
    }
  }
  
  // 汇总所有结果并发送一条消息
  const successCount = results.filter(r => r.success).length;
  const totalCount = results.length;
  
  let summaryMessage = `📊 **登录汇总**: ${successCount}/${totalCount} 个账号成功\n\n`;
  
  results.forEach(result => {
    summaryMessage += `${result.message}\n`;
  });
  
  console.log('\n📤 正在发送通知...');
  
  // 并行发送通知
  await Promise.all([
    sendTelegram(summaryMessage),
    sendPushPlus(summaryMessage)
  ]);
  
  console.log('\n✅ 所有账号处理完成！');
}

main().catch(console.error);
