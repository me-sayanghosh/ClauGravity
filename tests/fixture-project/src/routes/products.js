const express = require("express");
const Product = require("../models/Product");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();

// Defect 7: Unbounded query without pagination or limit
router.get("/", async (req, res) => {
  try {
    const products = await Product.find({});
    res.json(products);
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch products" });
  }
});

// Decoy 2: Route protected by router-level middleware
router.use("/manage", requireAuth);

router.post("/manage/featured", async (req, res) => {
  try {
    const { productId } = req.body;
    await Product.findByIdAndUpdate(productId, { isFeatured: true });
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: "Update failed" });
  }
});

module.exports = router;
