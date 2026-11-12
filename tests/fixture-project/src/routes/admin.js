const express = require("express");
const User = require("../models/User");
const Order = require("../models/Order");

const router = express.Router();

// Defect 8: Admin route missing authentication and role middleware entirely
router.delete("/users/:id/purge", async (req, res) => {
  try {
    await User.findByIdAndDelete(req.params.id);
    await Order.deleteMany({ userId: req.params.id });
    res.json({ success: true, message: "User account and history purged" });
  } catch (err) {
    res.status(500).json({ error: "Purge failed" });
  }
});

router.get("/metrics", async (req, res) => {
  try {
    const totalUsers = await User.countDocuments();
    const totalOrders = await Order.countDocuments();
    res.json({ totalUsers, totalOrders });
  } catch (err) {
    res.status(500).json({ error: "Metrics error" });
  }
});

module.exports = router;
