async function signOne(cookie, index) {
  for (const base of DOMAINS) {
    try {
      const http = axios.create({
        baseURL: base,
        timeout: 15000,
        headers: {
          'Cookie': cookie.trim(),
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': base + '/'
        }
      });

      let { data: html } = await http.get('/plugin.php?id=fx_checkin:list');

      const formhash = (html.match(/name="formhash" value="(\w{8})"/) || [])[1]
                    || (html.match(/formhash=(\w{8})/) || [])[1];
      if (!formhash) throw 'Cookie失效或formhash获取失败';

      // 增强版信息提取（兼容已签到和未签到两种页面）
      const todayRank = (html.match(/今日签到排名\D*(\d+)/) 
                      || html.match(/已签到\D*第\D*(\d+)\D*名/) 
                      || html.match(/第\D*(\d+)\D*名签到/) 
                      || [])[1] || '未知';

      const username = (html.match(/id="username">([^<]+)</) 
                     || html.match(/class="xw1">([^<]+)</) 
                     || html.match(/<em id="myusername">([^<]+)</) 
                     || [])[1]?.trim() || '未知用户';

      const contiDays = (html.match(/已连续签到\D*(\d+)/) 
                      || html.match(/连续签到\D*(\d+)/) 
                      || html.match(/连签\D*(\d+)/) 
                      || [])[1] || '0';

      const totalDays = (html.match(/累计签到\D*(\d+)/) 
                      || html.match(/总签到\D*(\d+)/) 
                      || html.match(/签到总数\D*(\d+)/) 
                      || html.match(/累计\D*(\d+)\D*天/)
                      || [])[1] || '0';

      const totalRank = (html.match(/个人排名\D*(\d+)/) 
                      || html.match(/总排名\D*(\d+)/) 
                      || html.match(/排名\D*(\d+)/) 
                      || html.match(/第\D*(\d+)\D*名/)
                      || [])[1] || '未知';

      // 执行签到（如果已经签到，这一步会直接返回成功或无操作）
      await http.get(`/plugin.php?id=fx_checkin:checkin&formhash=${formhash}&inajax=1`);

      // 签到后重新抓一次，确保拿到最新数据
      ({ data: html } = await http.get('/plugin.php?id=fx_checkin:list'));

      // 再次提取（用同样的鲁棒正则）
      const newConti = (html.match(/已连续签到\D*(\d+)/) 
                     || html.match(/连续签到\D*(\d+)/) 
                     || html.match(/连签\D*(\d+)/) 
                     || [])[1] || contiDays;

      const newTotal = (html.match(/累计签到\D*(\d+)/) 
                     || html.match(/总签到\D*(\d+)/) 
                     || html.match(/签到总数\D*(\d+)/) 
                     || html.match(/累计\D*(\d+)\D*天/)
                     || [])[1] || totalDays;

      const newTodayRank = (html.match(/今日签到排名\D*(\d+)/) 
                         || html.match(/已签到\D*第\D*(\d+)\D*名/) 
                         || html.match(/第\D*(\d+)\D*名签到/) 
                         || [])[1] || todayRank;

      const msg = `✅ 第${index}个账号签到成功（${username}）\n` +
                  `🏆 今日排名：第 <b>${newTodayRank}</b> 名\n` +
                  `🔥 连签：<b>${newConti}</b> 天（+1）\n` +
                  `📊 累计签到：<b>${newTotal}</b> 天\n` +
                  `🏅 个人总排名：<b>${totalRank}</b> 名\n` +
                  `🌐 域名：${base}`;

      console.log(msg);
      return msg;

    } catch (e) {
      if (base === DOMAINS[DOMAINS.length - 1]) {
        return `账号${index}\n❌ 全部域名失效：${e.message || e}`;
      }
    }
  }
}
