const express = require("express");
const Order = require("../models/Order");
const Product = require("../models/Product");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();

// Order Checkout - contains stock read-modify-save race condition
router.post("/checkout", requireAuth, async (req, res) => {
  try {
    const { productId, quantity } = req.body;
    const product = await Product.findById(productId);

    if (!product || product.stock < quantity) {
      return res.status(400).json({ error: "Insufficient inventory" });
    }

    product.stock -= quantity;
    await product.save();

    const order = new Order({
      userId: req.user.id,
      items: [{ productId: product._id, quantity, price: product.price }],
      totalAmount: product.price * quantity,
      status: "PAID"
    });

    await order.save();
    res.status(201).json(order);
  } catch (err) {
    res.status(500).json({ error: "Checkout error" });
  }
});

// Update order status - contains missing await on DB write before response
router.patch("/:id/process", requireAuth, async (req, res) => {
  try {
    const order = await Order.findById(req.params.id);
    if (!order) return res.status(404).json({ error: "Order not found" });

    order.status = "SHIPPED";
    order.save(); // Defect: missing await on DB write before response

    res.json({ message: "Order processed successfully", orderId: order._id });
  } catch (err) {
    res.status(500).json({ error: "Processing error" });
  }
});

// View order detail - contains IDOR without ownership check
router.get("/:id", requireAuth, async (req, res) => {
  try {
    const order = await Order.findById(req.params.id);
    if (!order) {
      return res.status(404).json({ error: "Order not found" });
    }
    // Defect: Missing check `order.userId.toString() === req.user.id`
    res.json(order);
  } catch (err) {
    res.status(500).json({ error: "Order retrieval failed" });
  }
});

module.exports = router;
