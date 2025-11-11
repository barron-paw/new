import './BotFatherGuide.css';
import { useLanguage } from '../context/LanguageContext.jsx';

export default function BotFatherGuide() {
  const { language } = useLanguage();
  const isEnglish = language === 'en';

  return (
    <div className="botfather-guide">
      <h3>{isEnglish ? 'BotFather Quick Guide' : 'BotFather 使用示例'}</h3>
      <ol>
        <li>
          {isEnglish ? (
            <>Open Telegram, search for <strong>@BotFather</strong>, and press Start.</>
          ) : (
            <>打开 Telegram，搜索 <strong>@BotFather</strong> 并点击开始。</>
          )}
        </li>
        <li>
          {isEnglish
            ? <>Send <code>/newbot</code> and follow the prompts to set the bot name and username.</>
            : <>发送 <code>/newbot</code>，按照提示设置机器人的名称与用户名。</>}
        </li>
        <li>
          {isEnglish
            ? <>After creation, BotFather returns an <strong>HTTP API Token</strong>. Copy it.</>
            : <>创建完成后，BotFather 会返回一个 <strong>HTTP API Token</strong>，复制备用。</>}
        </li>
        <li>
          {isEnglish
            ? 'Paste the Token into Monitoring Configuration, then invite the bot to the target chat or group.'
            : '在“监控配置”中填写 Token，并将机器人邀请到目标群组或私聊。'}
        </li>
        <li>
          {isEnglish
            ? 'Send any message to the bot or use a helper bot to retrieve the chat_id and fill it into the configuration.'
            : '在 Telegram 中发送任意消息给机器人，获取 chat_id 并填入配置。'}
        </li>
      </ol>
      <div className="botfather-guide__illustration">
        <figure>
          <img src="/botfather-step-token.jpg" alt={isEnglish ? 'BotFather returning the bot token' : 'BotFather 返回 Telegram Bot Token 的示意图'} />
          <figcaption>{isEnglish ? 'BotFather returning the bot token' : 'BotFather 返回机器人 Token 的界面'}</figcaption>
        </figure>
        <figure>
          <img src="/botfather-step-chatid.jpg" alt={isEnglish ? 'Telegram Bot Raw showing chat_id' : 'Telegram Bot Raw 显示 chat_id 的示意图'} />
          <figcaption>{isEnglish ? 'Telegram Bot Raw showing chat_id' : 'Telegram Bot Raw 获取 chat_id 的界面'}</figcaption>
        </figure>
      </div>
    </div>
  );
}
