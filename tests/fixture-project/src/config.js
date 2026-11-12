module.exports = {
  port: process.env.PORT || 3000,
  mongoUri: process.env.MONGO_URI || "mongodb://localhost:27017/store",
  jwtSecret: process.env.JWT_SECRET || "dev-jwt-insecure-secret-key-123",
  jwtExpiresIn: "2h"
};
