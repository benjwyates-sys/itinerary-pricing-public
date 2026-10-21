import { Sidebar } from "./ui/Sidebar";
import { PriceATrip } from "./screens/PriceATrip";
import { Preview } from "./screens/Preview";
import { Review } from "./screens/Review";
import { Costed } from "./screens/Costed";
import { Quotes } from "./screens/Quotes";
import { Admin } from "./screens/Admin";
import { useDemo } from "./store/demo";

export function App() {
  const screen = useDemo((state) => state.screen);

  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        {screen === "price" && <PriceATrip />}
        {screen === "preview" && <Preview />}
        {screen === "review" && <Review />}
        {screen === "costed" && <Costed />}
        {screen === "quotes" && <Quotes />}
        {screen === "admin" && <Admin />}
      </main>
    </div>
  );
}
