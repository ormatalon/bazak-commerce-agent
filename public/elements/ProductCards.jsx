// Product cards for the chat. Chainlit loads this file by name for
// cl.CustomElement(name="ProductCards", props={"products": [...]}) and gives it
// a global `props`. Only "react" and Chainlit's bundled libraries can be imported.
//
// Styling is all inline. Chainlit ships a pre-built Tailwind stylesheet, so a
// Tailwind class we use here only works if it was already in that build.
// Colors come from Chainlit's own theme variables, so light and dark both work.
import { useState } from "react";

// 1234.5 -> "$1,234.56"
const formatPrice = (price) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(price);

const styles = {
  // Columns of at least 220px, as many as fit: 1 on a phone, 2-3 on a desktop.
  // min(220px, 100%) keeps one column from overflowing a very narrow chat.
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(min(220px, 100%), 1fr))",
    gap: "12px",
    width: "100%",
    boxSizing: "border-box",
    textAlign: "left",
  },
  card: {
    display: "flex",
    flexDirection: "column",
    minWidth: 0, // lets long words wrap instead of widening the grid
    overflow: "hidden",
    borderRadius: "8px",
    border: "1px solid hsl(var(--border))",
    background: "hsl(var(--card))",
    color: "hsl(var(--card-foreground))",
  },
  // Fixed-shape box, so a missing or slow image never changes the layout.
  imageBox: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    aspectRatio: "4 / 3",
    background: "hsl(var(--muted))",
    color: "hsl(var(--muted-foreground))",
    fontSize: "13px",
  },
  image: { width: "100%", height: "100%", objectFit: "contain" },
  body: { display: "flex", flexDirection: "column", gap: "6px", padding: "12px" },
  title: { margin: 0, fontSize: "15px", fontWeight: 600, lineHeight: 1.3, overflowWrap: "anywhere" },
  brand: { fontSize: "12px", color: "hsl(var(--muted-foreground))" },
  description: {
    margin: 0,
    fontSize: "13px",
    lineHeight: 1.4,
    color: "hsl(var(--muted-foreground))",
    overflowWrap: "anywhere",
    // Show at most 2 lines, then "..."
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  },
  footer: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: "4px",
  },
  price: { fontSize: "17px", fontWeight: 700 },
  rating: { fontSize: "13px", color: "hsl(var(--muted-foreground))" },
};

function ProductCard({ product }) {
  // If the image fails to load, swap it for the "No image" box.
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = product.thumbnail && !imageFailed;

  return (
    <div dir="ltr" style={styles.card}>
      <div style={styles.imageBox}>
        {showImage ? (
          <img
            src={product.thumbnail}
            alt={product.title}
            loading="lazy"
            style={styles.image}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span>No image</span>
        )}
      </div>
      <div style={styles.body}>
        <h3 style={styles.title}>{product.title}</h3>
        {/* brand is null on about half of the catalog: show the line only if it exists */}
        {product.brand ? <div style={styles.brand}>{product.brand}</div> : null}
        <p style={styles.description}>{product.description}</p>
        <div style={styles.footer}>
          <span style={styles.price}>{formatPrice(product.price)}</span>
          {typeof product.rating === "number" ? (
            <span style={styles.rating}>{"★"} {product.rating.toFixed(1)}</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function ProductCards() {
  const products = props.products || [];
  if (products.length === 0) return null;

  return (
    <div dir="ltr" style={styles.grid}>
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
