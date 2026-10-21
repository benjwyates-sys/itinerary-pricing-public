import { useState } from "react";
import { Icon } from "./Icon";
import { useDemo, type Screen } from "../store/demo";

const NAV: { screen: Screen; label: string; icon: "price" | "quotes" | "admin" }[] = [
  { screen: "price", label: "Price a trip", icon: "price" },
  { screen: "quotes", label: "My quotes", icon: "quotes" },
  { screen: "admin", label: "Rate sheets", icon: "admin" },
];

export function Sidebar() {
  const [confirming, setConfirming] = useState(false);
  const screen = useDemo((state) => state.screen);
  const go = useDemo((state) => state.go);
  const resetDemo = useDemo((state) => state.resetDemo);

  // Screens 1, 2, 5 and 6 are the consultant; screen 4 is the same person
  // wearing the administrator's hat. That is the point the deck makes.
  const role = screen === "admin" ? "Administrator" : "Travel consultant";

  return (
    <nav className="sidebar">
      <div className="sidebar__top">
        <div className="sidebar__brand">
          <div className="sidebar__mark" />
          <span className="sidebar__name">Costing</span>
        </div>
        <div className="sidebar__nav">
          {NAV.map((item) => {
            const UNDER_PRICE: Screen[] = ["preview", "review", "costed"];
            const active =
              screen === item.screen ||
              (item.screen === "price" && UNDER_PRICE.includes(screen));
            return (
              <button
                key={item.screen}
                type="button"
                className={`navitem${active ? " navitem--active" : ""}`}
                onClick={() => go(item.screen)}
              >
                <Icon name={item.icon} color={active ? "#FFFFFF" : "#A2938E"} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="sidebar__bottom">
        {/* §8.8 — permanent, honest, and small. */}
        <span className="chip-demo">Demo · sample data</span>

        {/*
          Not optional (§3). The demo gets run repeatedly in front of people,
          and a half-finished previous run makes it look broken. Confirmed
          in-app rather than through a browser dialog, which would sit on top
          of the demo at exactly the wrong moment.
        */}
        {confirming ? (
          <div className="resetask">
            <span className="resetask__q">Clear everything and start over?</span>
            <div className="resetask__row">
              <button
                type="button"
                className="resetask__yes"
                onClick={() => {
                  resetDemo();
                  setConfirming(false);
                }}
              >
                Yes, reset
              </button>
              <button
                type="button"
                className="resetask__no"
                onClick={() => setConfirming(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="navitem" onClick={() => setConfirming(true)}>
            <Icon name="reset" color="#A2938E" />
            <span>Reset demo</span>
          </button>
        )}

        <div className="whoami">
          <div className="avatar">SA</div>
          <div>
            <div className="whoami__name">Sample Agent</div>
            <div className="whoami__role">{role}</div>
          </div>
        </div>
      </div>
    </nav>
  );
}
