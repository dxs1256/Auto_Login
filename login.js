const axios = require('axios');
const { chromium } = require('playwright');

// 从新的环境变量名称获取值
const token = process.env.TG_BOT_TOKEN; // 修改为 TG_BOT_TOKEN
const chatId = process.env.TG_CHAT_ID;   // 修改为 TG_CHAT_ID
const accounts = process.env.NETLIB_ACCOUNTS; // 修改为 NETLIB_ACCOUNTS

if (!accounts) {
  console.log('❌ 未配置账号 (环境变量 NETLIB_ACCOUNTS 缺失)'); // 提示信息也相应修改
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

async function sendTelegram(message) {
  if (!token || !chatId) {
    console.log('⚠️ Telegram Token 或 Chat ID 未配置，跳过发送通知。'); // 增加未配置时的提示
    return;
  }

  const now = new Date();
  const hkTime = new Date(now.getTime() + (8 * 60 * 60 * 1000));
  const timeStr = hkTime.toISOString().replace('T', ' ').substr(0, 19) + " HKT";

  const fullMessage = `🎉 Netlib 登录通知\n\n登录时间：${timeStr}\n\n${message}`;

  try {
    await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, {
      chat_id: chatId,
      text: fullMessage
    }, { timeout: 10000 });
    console.log('✅ Telegram 通知发送成功');
  } catch (e) {
    console.log('⚠️ Telegram 发送失败', e.message); // 打印错误信息
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
    page.setDefaultTimeout(30000); // 增加默认超时时间，避免一些网络波动导致的问题
    
    console.log(`📱 ${user} - 正在访问网站...`);
    await page.goto('https://www.netlib.re/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    
    console.log(`🔑 ${user} - 点击登录按钮...`);
    // 更健壮的选择器，以防文本改变
    const loginButton = await page.$('text=/Login/i, [role="button"], a:has-text("Login")'); 
    if (loginButton) {
      await loginButton.click({ timeout: 5000 });
    } else {
      console.log(`⚠️ ${user} - 未找到明确的登录按钮，尝试直接填写表单。`);
    }

    await page.waitForTimeout(2000);
    
    console.log(`📝 ${user} - 填写用户名...`);
    // 更通用的用户名输入框选择器
    await page.fill('input[name="username"], input[id*="user"], input[type="text"]', user);
    await page.waitForTimeout(1000);
    
    console.log(`🔒 ${user} - 填写密码...`);
    // 更通用的密码输入框选择器
    await page.fill('input[name="password"], input[id*="pass"], input[type="password"]', pass);
    await page.waitForTimeout(1000);
    
    console.log(`📤 ${user} - 提交登录...`);
    // 更通用的提交按钮选择器
    await page.click('button:has-text(/Validate|Login|Sign In/i), input[type="submit"], [type="submit"]');
    
    await page.waitForLoadState('networkidle'); // 等待网络空闲
    await page.waitForTimeout(5000); // 额外等待，确保页面完全加载和跳转
    
    // 检查登录是否成功
    const pageContent = await page.content();
    
    // 检查登录成功或失败的关键词，可以根据实际网站的登录反馈做更精确的判断
    // 例如，检查是否有个人中心链接，或者是否有错误提示
    if (pageContent.includes('exclusive owner') || pageContent.includes(user) || pageContent.includes('My Account')) {
      console.log(`✅ ${user} - 登录成功`);
      result.success = true;
      result.message = `✅ ${user} 登录成功`;
    } else if (pageContent.includes('Invalid username or password') || pageContent.includes('Incorrect login')) {
      console.log(`❌ ${user} - 登录失败: 用户名或密码错误`);
      result.message = `❌ ${user} 登录失败: 用户名或密码错误`;
    } 
    else {
      // 捕获其他未知的登录失败情况
      console.log(`❌ ${user} - 登录失败 (未知原因，请检查页面内容)`);
      result.message = `❌ ${user} 登录失败 (未知原因)`;
    }
    
  } catch (e) {
    console.log(`❌ ${user} - 登录异常: ${e.message}`);
    result.message = `❌ ${user} 登录异常: ${e.message}`;
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
  
  let summaryMessage = `📊 登录汇总: ${successCount}/${totalCount} 个账号成功\n\n`;
  
  results.forEach(result => {
    summaryMessage += `${result.message}\n`;
  });
  
  await sendTelegram(summaryMessage);
  
  console.log('\n✅ 所有账号处理完成！');
}

main().catch(console.error);
