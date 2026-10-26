import { navigate } from "../../router";
import { Icon, SectionTitle } from "../../ui";
import { ADD_DATA, REPORTS, type QuickAction } from "../quickActions";

/** One labelled row of shortcut pills that scrolls sideways when it does not fit. */
function ActionRow({ id, title, actions, onAction }: { id: string; title: string; actions: QuickAction[]; onAction: (a: QuickAction) => void }) {
  return (
    <section className="home-section" aria-labelledby={id}>
      <SectionTitle id={id}>{title}</SectionTitle>
      <div className="home-actions ui-bleed" role="group" aria-labelledby={id}>
        {actions.map((action) => (
          <button key={action.label} type="button" className={`home-action${action.primary ? " is-primary" : ""}`} onClick={() => onAction(action)}>
            <Icon name={action.icon} size={15} />
            {action.label}
          </button>
        ))}
      </div>
    </section>
  );
}

/** Home before a question is asked (the owner's picture): the "Add data" and "Report" rows, nothing else. */
export function HomeIntro({ onUpload, onChat }: { onUpload: () => void; onChat: () => void }) {
  const act = (action: QuickAction) => {
    if (action.go === "upload") onUpload();
    else if (action.go === "chat") onChat();
    else navigate(action.go);
  };
  return (
    <>
      <ActionRow id="home-add" title="Add data" actions={ADD_DATA} onAction={act} />
      <ActionRow id="home-report" title="Report" actions={REPORTS} onAction={act} />
    </>
  );
}
