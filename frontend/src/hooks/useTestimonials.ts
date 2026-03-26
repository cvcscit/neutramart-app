// hooks/useTestimonials.ts
import { useEffect, useState } from "react";

type Testimonial = { text: string; image: string; name: string; role: string };

export function useTestimonials() {
  const [testimonials, setTestimonials] = useState<Testimonial[]>([]);

  useEffect(() => {
    fetch("/api/testimonials")
      .then((r) => r.json())
      .then(setTestimonials);
  }, []);

  return testimonials;
}
