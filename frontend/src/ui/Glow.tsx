import "./Glow.css";

/** The design's ambient light: a violet glow top-right and a gold one top-left of the content column. */
export function Glow() {
  return (
    <div className="ui-glow" aria-hidden="true">
      <span className="ui-glow__brand" />
      <span className="ui-glow__gold" />
    </div>
  );
}
