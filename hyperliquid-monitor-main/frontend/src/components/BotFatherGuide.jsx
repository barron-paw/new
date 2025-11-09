import './BotFatherGuide.css';

export default function BotFatherGuide() {
  return (
    <div className="botfather-guide">
      <h3>BotFather 使用示例</h3>
      <ol>
        <li>打开 Telegram，搜索 <strong>@BotFather</strong> 并点击开始。</li>
        <li>发送 <code>/newbot</code>，按照提示设置机器人的名称与用户名。</li>
        <li>创建完成后，BotFather 会返回一个 <strong>HTTP API Token</strong>，复制备用。</li>
        <li>在“监控配置”中填写 Token，并将机器人邀请到目标群组或私聊。</li>
        <li>在 Telegram 中发送任意消息给机器人，获取 <code>chat_id</code> 并填入配置。</li>
      </ol>
      <div className="botfather-guide__illustration">
        <figure>
          <img src="/botfather-step-token.jpg" alt="BotFather 返回 Telegram Bot Token 的示意图" />
          <figcaption>BotFather 返回机器人 Token 的界面</figcaption>
        </figure>
        <figure>
          <img src="/botfather-step-chatid.jpg" alt="Telegram Bot Raw 显示 chat_id 的示意图" />
          <figcaption>Telegram Bot Raw 获取 chat_id 的界面</figcaption>
        </figure>
      </div>
    </div>
  );
}
