import './BotFatherGuide.css';
import { useLanguage } from '../context/LanguageContext.jsx';

export default function BotFatherGuide({ usesDefaultBot = false, defaultBotUsername = '' }) {
  const { language } = useLanguage();
  const isEnglish = language === 'en';
  const hasBotName = Boolean(defaultBotUsername);

  return (
    <div className="botfather-guide">
      <h3>{isEnglish ? 'Telegram Chat ID Guide' : 'Telegram Chat ID 获取指南'}</h3>
      <ol>
        {usesDefaultBot ? (
          <li>
            {isEnglish ? (
              hasBotName ? (
                <>
                  Search for <strong>{defaultBotUsername}</strong> in Telegram and press <em>Start</em> once so the bot can message you.
                </>
              ) : (
                <>
                  Open the official monitoring bot in Telegram and press <em>Start</em> once to activate it for your chat.
                </>
              )
            ) : hasBotName ? (
              <>
                在 Telegram 搜索 <strong>{defaultBotUsername}</strong> 并点击 <em>Start</em> 激活机器人。
              </>
            ) : (
              <>打开系统默认机器人，点击 <em>Start</em> 以便后端能够向您推送消息。</>
            )}
          </li>
        ) : null}
        <li>
          {isEnglish ? (
            <>
              Talk to <strong>@TelegramBotRaw</strong> (or any bot that returns chat IDs) and send an arbitrary message. The bot will reply with your <code>chat_id</code>.
            </>
          ) : (
            <>
              在 Telegram 中与 <strong>@TelegramBotRaw</strong> 对话，发送任意消息后即可获得返回的 <code>chat_id</code>。
            </>
          )}
        </li>
        <li>
          {isEnglish
            ? 'Copy the chat_id into the Monitoring Configuration form, enter wallet addresses, and save.'
            : '将 chat_id 粘贴到监控配置中，填写钱包地址后保存即可。'}
        </li>
      </ol>
      <div className="botfather-guide__illustration">
        <figure>
          <img
            src="https://raw.githubusercontent.com/barron-paw/new/main/6f9d09a6b016f25aa5c8726901a7bb66.jpg"
            alt={isEnglish ? 'Telegram Bot Raw returning chat_id' : 'Telegram Bot Raw 返回 chat_id 的界面'}
          />
          <figcaption>{isEnglish ? 'Telegram Bot Raw returning the chat_id' : '通过 Telegram Bot Raw 获取 chat_id'}</figcaption>
        </figure>
        <figure>
          <img
            src="https://raw.githubusercontent.com/barron-paw/new/main/2.jpg"
            alt={isEnglish ? 'Copy the chat_id into configuration' : '复制 chat_id 并粘贴到监控配置'}
          />
          <figcaption>{isEnglish ? 'Copy the chat_id and paste it into the monitoring form.' : '复制 chat_id，粘贴到监控配置表单中。'}</figcaption>
        </figure>
      </div>
    </div>
  );
}
