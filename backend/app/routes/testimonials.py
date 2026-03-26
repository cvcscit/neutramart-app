from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/testimonials")
async def get_testimonials():
    testimonials = [
    {
      "text": "This app completely changed how I approach my nutrition. Tracking calories and macros is simple, and I finally feel in control of my eating habits.",
      "image": "https://randomuser.me/api/portraits/women/1.jpg",
      "name": "Briana Patton",
      "role": "Fitness Enthusiast",
    },
    {
      "text": "I love how intuitive the food logging is. Scanning barcodes and tracking meals takes seconds, which makes staying consistent effortless.",
      "image": "https://randomuser.me/api/portraits/men/2.jpg",
      "name": "Bilal Ahmed",
      "role": "Busy Professional",
    },
    {
      "text": "The insights and daily summaries helped me understand my eating patterns better. It’s motivating without being overwhelming.",
      "image": "https://randomuser.me/api/portraits/women/3.jpg",
      "name": "Saman Malik",
      "role": "Health-Conscious User",
    },
    {
      "text": "As someone focused on weight loss, this app keeps me accountable. Seeing my calorie intake visually has made a huge difference.",
      "image": "https://randomuser.me/api/portraits/men/4.jpg",
      "name": "Omar Raza",
      "role": "Weight Loss Journey",
    },
    {
      "text": "Tracking macros used to be confusing, but this app makes it clear and easy. It’s been a game-changer for my workouts and recovery.",
      "image": "https://randomuser.me/api/portraits/women/5.jpg",
      "name": "Zainab Hussain",
      "role": "Gym Regular",
    },
    {
      "text": "I appreciate how customizable the goals are. Whether it’s calories, protein, or water intake, everything fits my lifestyle.",
      "image": "https://randomuser.me/api/portraits/women/6.jpg",
      "name": "Aliza Khan",
      "role": "Wellness Advocate",
    },
    {
      "text": "The clean design and reminders help me stay consistent every day. It feels more like a habit coach than just a tracking app.",
      "image": "https://randomuser.me/api/portraits/men/7.jpg",
      "name": "Farhan Siddiqui",
      "role": "University Student",
    },
    {
      "text": "I’ve tried many calorie trackers, but this one stands out for how simple and motivating it is to use daily.",
      "image": "https://randomuser.me/api/portraits/women/8.jpg",
      "name": "Sana Sheikh",
      "role": "Lifestyle Blogger",
    },
    {
      "text": "Being able to track meals on the go has helped me stay consistent even on busy days. Highly recommend it to anyone serious about nutrition.",
      "image": "https://randomuser.me/api/portraits/men/9.jpg",
      "name": "Hassan Ali",
      "role": "Entrepreneur",
    }
  ]
    return testimonials
