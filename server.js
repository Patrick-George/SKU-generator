const path = require("path");
const express = require("express");
const session = require("express-session");
const pages = require("./routes/pages");
const admin = require("./routes/admin");

const app = express();
const port = process.env.PORT || 3000;

app.set("trust proxy", 1);
app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.use(express.urlencoded({ extended: true, limit: "20mb" }));
app.use(express.static(path.join(__dirname, "public")));
app.use(session({
  secret: process.env.SESSION_SECRET || "blastline-sku-session",
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: "lax", maxAge: 7 * 24 * 60 * 60 * 1000 },
}));

app.use((req, res, next) => {
  res.locals.admin = Boolean(req.session.admin);
  res.locals.flash = req.session.flash || null;
  delete req.session.flash;
  next();
});

app.get("/login", (req, res) => {
  if (req.session.admin) return res.redirect("/admin");
  res.render("login", { title: "Admin Login", page: "login" });
});

app.post("/login", (req, res) => {
  const expected = process.env.ADMIN_PASSWORD || "admin123";
  if (req.body.password === expected) {
    req.session.admin = true;
    return res.redirect("/admin");
  }
  req.session.flash = { type: "err", text: "Invalid password." };
  res.redirect("/login");
});

app.post("/logout", (req, res) => {
  req.session.admin = false;
  res.redirect("/");
});

app.use(pages);
app.use("/admin", admin);

app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).send("Something went wrong.");
});

app.listen(port, () => {
  console.log(`Blastline SKU Configurator listening on ${port}`);
});
