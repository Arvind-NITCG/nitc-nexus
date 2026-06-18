require("dotenv").config();

const express = require("express");
const axios = require("axios");

const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3000;
const BOT_TOKEN = process.env.BOT_TOKEN;

app.get("/", (req, res) => {
  res.send("Bot server is running");
});

app.post("/webhook", async (req, res) => {
  try {
    const message = req.body.message;

    if (!message) {
      return res.sendStatus(200);
    }

    const chatId = message.chat.id;
    const userText = message.text;

    const reply = `User says: ${userText}`;

    await axios.post(
      `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`,
      {
        chat_id: chatId,
        text: reply,
      }
    );

    res.sendStatus(200);
  } catch (err) {
    console.error(err);
    res.sendStatus(500);
  }
});

app.listen(PORT, () => {
  console.log("Server running");
});
