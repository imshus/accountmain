import { navigate } from "../../router";
import { Icon } from "../../ui";

/** Above an open conversation: its title, the past chats and a new chat. */
export function HomeChatBar({ title, onNew }: { title: string; onNew: () => void }) {
  return (
    <div className="home-chatbar">
      <h1 className="home-chatbar__title" title={title}>
        {title || "Conversation"}
      </h1>
      <button type="button" className="home-chatbar__btn" onClick={() => navigate({ name: "history" })} aria-label="Past chats" title="Past chats">
        <Icon name="clock" size={18} />
      </button>
      <button type="button" className="home-chatbar__btn is-new" onClick={onNew} title="New chat">
        <Icon name="edit" size={16} />
        <span>New chat</span>
      </button>
    </div>
  );
}
