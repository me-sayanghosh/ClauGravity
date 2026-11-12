const express = require("express");
const jwt = require("jsonwebtoken");
const User = require("../models/User");
const config = require("../config");

const router = express.Router();

router.post("/login", async (req, res) => {
  try {
    const user = await User.findOne(req.body);
    if (!user) {
      return res.status(401).json({ error: "Invalid credentials" });
    }

    const token = jwt.sign(
      { id: user._id, role: user.role, email: user.email },
      config.jwtSecret,
      { expiresIn: config.jwtExpiresIn }
    );

    res.json({ token, user: { id: user._id, username: user.username, role: user.role } });
  } catch (err) {
    res.status(500).json({ error: "Authentication failed" });
  }
});

// Decoy 1: Parameterized safe lookup that appears dynamic
router.get("/user-check", async (req, res) => {
  try {
    const safeUsername = String(req.query.username || "").trim();
    if (!safeUsername) {
      return res.status(400).json({ error: "Username required" });
    }
    const user = await User.findOne({ username: safeUsername }).select("username createdAt");
    res.json({ exists: Boolean(user) });
  } catch (err) {
    res.status(500).json({ error: "Lookup error" });
  }
});

module.exports = router;
