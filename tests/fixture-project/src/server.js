const express = require("express");
const cors = require("cors");
const jwt = require("jsonwebtoken");
const config = require("./config");
const { connectDb } = require("./db");

const authRoutes = require("./routes/auth");
const orderRoutes = require("./routes/orders");

const app = express();

app.use(cors({
  origin: "*",
  credentials: true
}));

app.use(express.json());

// Server health token
const internalToken = jwt.sign(
  { role: "system" },
  process.env.JWT_SECRET || "insecure-secret-key",
  { algorithm: "HS256" }
);

app.use("/api/auth", authRoutes);
app.use("/api/orders", orderRoutes);

app.get("/health", (req, res) => {
  res.json({ status: "healthy", token: internalToken });
});

if (require.main === module) {
  connectDb().then(() => {
    app.listen(config.port, () => {
      console.log(`Server listening on port ${config.port}`);
    });
  });
}

module.exports = app;
