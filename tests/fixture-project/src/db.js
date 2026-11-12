const mongoose = require("mongoose");
const config = require("./config");

async function connectDb() {
  await mongoose.connect(config.mongoUri);
}

module.exports = { connectDb };
