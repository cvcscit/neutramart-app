import { GridMotion } from "./ui/grid-motion";
import demo1 from "@/assets/images/demo-1.png";
import demo2 from "@/assets/images/demo-2.png";
import demo3 from "@/assets/images/demo-3.png";
import demo4 from "@/assets/images/demo-4.png";
import demo5 from "@/assets/images/demo-5.png";

export default function AppGrid() {
  const items = [
    <img
      key="demo-2-1"
      src={demo2}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    <img
      key="demo-1-1"
      src={demo1}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    <img
      key="demo-2-2"
      src={demo5}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    <img
      key="demo-1-2"
      src={demo4}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    <img
      key="demo-1-2"
      src={demo3}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    "https://i.pinimg.com/736x/ef/83/58/ef83581cc50e65c3a26632213bcd2f70.jpg",

    <img
      key="demo-1-2"
      src={demo2}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    <img
      key="demo-1-2"
      src={demo4}
      alt="Demo"
      className="w-full h-full object-cover"
    />,

    <img
      key="demo-5-1"
      src={demo5}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    <img
      key="demo-5-2"
      src={demo5}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
    "https://i.pinimg.com/736x/6c/c5/44/6cc54409c381b6386c81d898309113e2.jpg",
    <img
      key="demo-4-1"
      src={demo4}
      alt="Demo"
      className="w-full h-full object-cover"
    />,
  ];

  return (
    <div className="sm:flex hidden space-y-8">
      <div className="h-screen w-full bg-gradient-to-br from-background to-muted">
        <GridMotion
          items={items}
          gradientColor="hsl(var(--brand))"
          className="relative z-10 backdrop-blur-sm"
        />
      </div>
    </div>
  );
}
