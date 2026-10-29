# W360: What the Platform Does

W360 is a personal wellness assistant. People photograph their meals, check their vitals with a short face scan, and chat with an AI assistant that knows their history. This overview describes what the system does, in plain language.

---

## The main capabilities

### 1. Meal scanning
A user takes a photo of their food. Within seconds, W360 tells them:
- what the dish is
- calories, protein, carbs, fat, fiber and sugar
- key vitamins and minerals (iron, calcium, vitamin C and others)

Each scan is added to the user's food history automatically. Users can also save meals under their own names, such as "Monday lunch", and delete them later.

### 2. Vitals check
The user looks into their phone or laptop camera for about a minute. W360 estimates:
- heart rate
- blood pressure
- heart rate variability (a common stress and recovery indicator)
- breathing rate
- stress level

The scan runs on the user's own device and the video is never uploaded. Only the resulting numbers are saved.

> These readings are wellness estimates, not medical measurements. They are not a substitute for a doctor or a medical device.

### 3. AI assistant (chat)
Users can ask questions in everyday language, for example:
- "How was my protein this week?"
- "What should I eat for dinner?"
- "Is my heart rate okay?"

The assistant answers using the user's own data: past meals, nutrition trends and vitals. If a reading looks concerning, such as a very high heart rate, it says so clearly. It suggests food and lifestyle changes and recommends seeing a doctor.

### 4. Charts and stats
A built-in dashboard shows:
- calories and macronutrients over time
- heart rate and blood pressure trends

Users can view their data by day, week or month, or pick their own date range. They can also ask the assistant for a chart, for example "plot my heart rate", and it appears in the conversation.

### 5. Weekly summary
W360 can write a short weekly recap of the user's eating patterns, covering what went well and what to improve.

---

## How a typical user experience works

1. **Sign in** with a Google account. No new password is needed.
2. **Snap a meal** to get an instant nutrition breakdown, saved automatically.
3. **Run a vitals check** whenever they like. It takes about a minute.
4. **Ask the assistant** anything about their food or health habits.
5. **Open "My stats"** to see trends over days, weeks or months.

---

## Privacy and data handling

- **Sign-in:** users sign in through Google. W360 never sees or stores their password.
- **Data is stored in the user's region:** each person's records are kept in their own geographic region (for example, India, Europe, Canada or the US).
- **Users only see their own data.** Every request is tied to the signed-in user, and no one can access another person's records.
- **Face scan video is not uploaded.** The vitals analysis happens on the user's device. Only the resulting numbers are stored.
- **Secure connections:** users connect to W360 only over HTTPS, and plain-HTTP requests are automatically redirected to HTTPS.

---

## Technology and security

W360 runs entirely on **Amazon Web Services (AWS)**, using managed services built for security and scale.

### The technology stack

| Layer | AWS service | What it does |
|---|---|---|
| Front door | **Amazon CloudFront** | A global content delivery network. Serves the app and API from locations close to users, enforces HTTPS, and absorbs traffic spikes. |
| API servers | **Amazon ECS on AWS Fargate**, behind an **Application Load Balancer** | Runs the W360 API in managed containers. There are no servers to patch, it scales automatically, and unhealthy instances are replaced. |
| Data storage | **Amazon S3** (one storage location per region) | Stores meal history, scans and vitals, separately in each region to keep data local. |
| AI | **Amazon Bedrock** and **Bedrock AgentCore** | Runs the AI that powers food recognition and the assistant. The assistant runs in the user's region, and AWS does not use customer data to train AI models. |
| Access control | **AWS IAM** | Each component gets only the permissions it needs, and nothing more. |
| Sign-in | **Google Sign-In** | Industry-standard secure login. W360 never handles passwords. |

### How data is protected while it moves

- **App and browser to W360:** encrypted with HTTPS (TLS). Insecure HTTP connections are redirected to HTTPS.
- **Photo uploads:** go straight from the user's device to secure storage over HTTPS, using single-use upload links that expire after 5 minutes.
- **Calls to the AI and storage services:** run inside AWS over encrypted (TLS) connections.
- **Face scan video:** never transferred. It's processed on the device.

### How data is protected at rest

- All stored data is encrypted with **AES-256**.
- Each user's data is stored in their own region and kept separate from every other user's.

### Other safeguards

- **Verified identity on every request:** each API call must carry a valid Google sign-in token, and expired or forged tokens are rejected.
- **The servers can't be reached directly:** they accept traffic only through the CloudFront front door.
- **Rate limiting:** blocks abuse and keeps the service fast for everyone.
- **Least-privilege access:** automated deployments and each service get narrowly scoped, temporary credentials. No long-lived passwords or keys are stored in the deployment pipeline.

---

## Fair-use limits

To keep the service fast and reliable for everyone, there are generous limits on usage. For example, each user can scan up to 1,000 food photos per day, far more than normal use. Users who hit a limit see a friendly message asking them to try again shortly.

---

## For integration partners

Any app or website can connect to these same capabilities through a secure API. Partners receive technical documentation and access details separately from the W360 team.
