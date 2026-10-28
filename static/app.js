/* Offline, dependency-free charts. All source values arrive through Django json_script. */
(() => {
  const menu = document.querySelector(".menu-toggle");
  menu?.addEventListener("click", () => {
    const open = document.querySelector(".sidebar").classList.toggle("open");
    menu.setAttribute("aria-expanded", String(open));
  });
  const source = document.getElementById("chart-data");
  if (source) {
    const data = JSON.parse(source.textContent);
    const renderCharts = () =>
      document.querySelectorAll("[data-chart]").forEach((container) => {
        container.replaceChildren();
        draw(container, data);
      });
    renderCharts();
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(renderCharts, 150);
    });
  }
  function draw(container, data) {
    if (!data?.labels?.length) {
      container.textContent = "No chart data available yet.";
      return;
    }
    const w = Math.max(300, container.clientWidth - 30),
      h = 270,
      pad = { l: 44, r: 22, t: 25, b: 35 };
    const max = Math.max(
      1,
      ...[
        ...(data.actual || []),
        ...(data.forecast || []),
        ...(!data.aggregate ? data.upper || [] : []),
      ].filter((x) => x !== null),
    );
    const ceiling = Math.ceil(max / 5) * 5;
    const x = (i) =>
      pad.l + (i / Math.max(1, data.labels.length - 1)) * (w - pad.l - pad.r);
    const y = (value) => h - pad.b - (value / ceiling) * (h - pad.t - pad.b);
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("preserveAspectRatio", "none");
    const add = (tag, attrs, content) => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attrs).forEach(([key, value]) =>
        node.setAttribute(key, String(value)),
      );
      if (content !== undefined) node.textContent = content;
      svg.append(node);
      return node;
    };
    if (
      data.boundary !== null &&
      data.boundary !== undefined &&
      data.forecast?.some((v) => v !== null)
    ) {
      add("rect", {
        x: x(data.boundary),
        y: pad.t,
        width: w - pad.r - x(data.boundary),
        height: h - pad.b - pad.t,
        fill: "#f0f3e7",
        stroke: "none",
        rx: 3,
      });
      add(
        "text",
        {
          x: x(data.boundary) + 7,
          y: pad.t + 10,
          fill: "#768259",
          stroke: "none",
          "font-size": 8,
          "font-family": "Segoe UI, sans-serif",
          "letter-spacing": 1,
        },
        w < 450 ? "OUTLOOK" : "FORECAST WINDOW",
      );
    }
    for (let i = 0; i <= 4; i++) {
      const val = (ceiling * i) / 4;
      add("line", {
        x1: pad.l,
        x2: w - pad.r,
        y1: y(val),
        y2: y(val),
        stroke: "#e9ede2",
        "stroke-dasharray": "3 5",
      });
      add(
        "text",
        {
          x: pad.l - 12,
          y: y(val) + 3,
          "text-anchor": "end",
          fill: "#a0a792",
          stroke: "none",
          "font-size": 9,
          "font-family": "Segoe UI, sans-serif",
        },
        Math.round(val).toLocaleString(),
      );
    }
    if (!data.aggregate && data.lower?.length && data.upper?.length) {
      const indices = data.lower
        .map((v, i) => (v === null ? null : i))
        .filter((v) => v !== null);
      if (indices.length)
        add("path", {
          d:
            "M" +
            indices.map((i) => `${x(i)},${y(data.upper[i])}`).join(" L") +
            " L" +
            [...indices]
              .reverse()
              .map((i) => `${x(i)},${y(data.lower[i])}`)
              .join(" L") +
            " Z",
          fill: "#d9e5bc",
          opacity: 0.55,
          stroke: "none",
        });
    }
    function line(values, color, dashed) {
      let path = "",
        gap = true;
      values.forEach((v, i) => {
        if (v === null || v === undefined) {
          gap = true;
          return;
        }
        path += (gap ? "M" : " L") + `${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        gap = false;
      });
      if (path)
        add("path", {
          d: path,
          stroke: color,
          fill: "none",
          "stroke-width": 2.1,
          "stroke-dasharray": dashed ? "5 5" : "none",
          "vector-effect": "non-scaling-stroke",
        });
    }
    line(data.actual || [], "#678559", false);
    line(data.forecast || [], "#b38c5a", true);
    const ticks = w < 450 ? 4 : 6;
    for (let i = 0; i < ticks; i++) {
      const index = Math.round(((data.labels.length - 1) * i) / (ticks - 1));
      const raw = data.labels[index];
      const label = raw.includes("-")
        ? new Date(raw + "T00:00:00").toLocaleDateString("en-GB", {
            day: "numeric",
            month: "short",
          })
        : `Day ${raw}`;
      add(
        "text",
        {
          x: x(index),
          y: h - 10,
          "text-anchor": "middle",
          fill: "#a0a792",
          stroke: "none",
          "font-size": 9,
          "font-family": "Segoe UI, sans-serif",
        },
        label,
      );
    }
    const cursor = add("line", {
      x1: 0,
      x2: 0,
      y1: pad.t,
      y2: h - pad.b,
      stroke: "#a2b18d",
      "stroke-dasharray": "3 3",
      visibility: "hidden",
    });
    const tip = document.createElement("div");
    tip.className = "chart-tooltip";
    tip.hidden = true;
    container.append(svg, tip);
    container.onpointermove = (event) => {
      const rect = svg.getBoundingClientRect();
      const relative = ((event.clientX - rect.left) / rect.width) * w;
      const i = Math.max(
        0,
        Math.min(
          data.labels.length - 1,
          Math.round(
            ((relative - pad.l) / (w - pad.l - pad.r)) *
              (data.labels.length - 1),
          ),
        ),
      );
      cursor.setAttribute("x1", x(i));
      cursor.setAttribute("x2", x(i));
      cursor.setAttribute("visibility", "visible");
      const value = data.actual?.[i] ?? data.forecast?.[i];
      tip.replaceChildren();
      const label = document.createElement("b");
      label.textContent = data.labels[i];
      tip.append(
        label,
        document.createElement("br"),
        `${data.actual?.[i] != null ? "Observed" : "Forecast"}: ${Math.round(value || 0).toLocaleString()} units`,
      );
      tip.style.left =
        Math.min(
          Math.max(
            0,
            event.clientX - container.getBoundingClientRect().left + 12,
          ),
          container.clientWidth - 150,
        ) + "px";
      tip.style.top = "35px";
      tip.hidden = false;
    };
    container.onpointerleave = () => {
      tip.hidden = true;
      cursor.setAttribute("visibility", "hidden");
    };
  }
  document.querySelectorAll("[data-job]").forEach((element) => {
    const id = element.dataset.job;
    const poll = async () => {
      try {
        const response = await fetch(`/api/jobs/${id}/`, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        const job = await response.json();
        const label = element.querySelector("[data-job-status]");
        if (label) label.textContent = job.status;
        if (["queued", "running"].includes(job.status)) setTimeout(poll, 4000);
        else {
          const link = document.createElement("a");
          link.href = location.href;
          link.textContent = " · Refresh results ↻";
          element.append(link);
        }
      } catch (_) {
        /* Status is also available through a normal page refresh. */
      }
    };
    setTimeout(poll, 4000);
  });
})();
