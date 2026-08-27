const NODE_LAYOUT = [
  ["resolver", "→", "planner"],
  [
    "fundamentals",
    "market_data",
    "competition",
    "risk"
  ],
  [
    "merge",
    "→",
    "assumption_builder",
    "→",
    "valuation"
  ],
  [
    "verification",
    "→",
    "critic",
    "→",
    "typed_router"
  ],
  [
    "success_final",
    "insufficient_final"
  ]
];

const NODE_LABELS = {
  resolver: "Resolver",
  planner: "Planner",
  fundamentals: "Financial Data",
  market_data: "Market Data",
  competition: "Competition",
  risk: "Risk",
  merge: "Evidence Hub",
  assumption_builder: "Assumption Builder",
  valuation: "Python Valuation",
  verification: "Verifier",
  critic: "LLM Critic",
  typed_router: "Typed Issue Router",
  success_final: "Final",
  insufficient_final: "Insufficient"
};

const graphEl =
  document.querySelector("#graph");

const timelineEl =
  document.querySelector("#timeline");

const statusBadge =
  document.querySelector("#statusBadge");

const runButton =
  document.querySelector("#runButton");

const identityCard =
  document.querySelector("#identityCard");

const metricsEl =
  document.querySelector("#metrics");

const finalAnswerEl =
  document.querySelector("#finalAnswer");

const verificationEl =
  document.querySelector("#verificationCard");

const valuationBarsEl =
  document.querySelector("#valuationBars");

const elapsedEl =
  document.querySelector("#elapsed");

let startTime = 0;
let timer = null;
let currentNode = null;


function esc(value) {
  return String(
    value ?? ""
  ).replace(
    /[&<>"']/g,
    char => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    }[char])
  );
}


function renderGraph() {
  graphEl.innerHTML = "";

  NODE_LAYOUT.forEach(
    row => {
      const rowEl =
        document.createElement(
          "div"
        );

      rowEl.className =
        "graph-row";

      row.forEach(
        item => {
          if (item === "→") {
            const arrow =
              document.createElement(
                "span"
              );

            arrow.className =
              "arrow";

            arrow.textContent =
              "→";

            rowEl.appendChild(
              arrow
            );

            return;
          }

          const node =
            document.createElement(
              "div"
            );

          node.className =
            "node";

          node.id =
            `node-${item}`;

          node.textContent =
            NODE_LABELS[item]
            ||
            item;

          rowEl.appendChild(
            node
          );
        }
      );

      graphEl.appendChild(
        rowEl
      );
    }
  );
}


function setNode(
  nodeName,
  state = "active"
) {
  if (
    currentNode
    &&
    currentNode !== nodeName
  ) {
    const previous =
      document.querySelector(
        `#node-${currentNode}`
      );

    previous?.classList.remove(
      "active"
    );

    previous?.classList.add(
      "done"
    );
  }

  const node =
    document.querySelector(
      `#node-${nodeName}`
    );

  if (!node) {
    return;
  }

  node.classList.remove(
    "done",
    "error",
    "active"
  );

  node.classList.add(
    state
  );

  currentNode =
    nodeName;
}


function addEvent(
  name,
  detail = "",
  state = "active"
) {
  const element =
    document.createElement(
      "div"
    );

  element.className =
    `event ${state}`;

  element.innerHTML =
    `
      <div class="name">
        ${esc(name)}
      </div>

      <div class="detail">
        ${esc(detail)}
      </div>
    `;

  timelineEl.prepend(
    element
  );
}


function setStatus(
  text,
  className
) {
  statusBadge.textContent =
    text;

  statusBadge.className =
    `badge ${className}`;
}


function showIdentity(identity) {
  identityCard.classList.remove(
    "hidden"
  );

  const items = [
    [
      "Status",
      identity.status
    ],
    [
      "Company",
      identity.company_name
    ],
    [
      "Ticker",
      identity.ticker
    ],
    [
      "Exchange",
      identity.exchange
    ],
    [
      "Currency",
      identity.currency
    ],
    [
      "Country",
      identity.country
    ],
    [
      "Confidence",
      identity.confidence != null
        ?
        Number(
          identity.confidence
        ).toFixed(2)
        :
        "-"
    ]
  ];

  let html =
    items.map(
      ([key, value]) =>
        `
          <div class="identity-item">
            <strong>${esc(key)}</strong>
            ${esc(value || "-")}
          </div>
        `
    ).join("");

  const candidates =
    identity.candidates
    ||
    [];

  if (candidates.length) {
    html +=
      `
        <div class="identity-item">
          <strong>Candidates</strong>
          ${esc(
            candidates
              .map(
                item =>
                  item.ticker
                  ||
                  item.name
                  ||
                  JSON.stringify(
                    item
                  )
              )
              .join(" / ")
          )}
        </div>
      `;
  }

  identityCard.innerHTML =
    html;
}


function metric(
  label,
  value
) {
  return `
    <div class="metric">
      <div class="label">
        ${esc(label)}
      </div>
      <div class="value">
        ${esc(value)}
      </div>
    </div>
  `;
}


function fmtB(value) {
  return (
    typeof value === "number"
    &&
    Number.isFinite(value)
  )
    ?
    `$${value.toFixed(1)}B`
    :
    "-";
}


function fmtX(value) {
  return (
    typeof value === "number"
    &&
    Number.isFinite(value)
  )
    ?
    `${value.toFixed(2)}x`
    :
    "-";
}


function fmtPct(value) {
  return (
    typeof value === "number"
    &&
    Number.isFinite(value)
  )
    ?
    `${(value * 100).toFixed(2)}%`
    :
    "-";
}


function renderResults(state) {
  const valuation =
    state.valuation_result
    ||
    {};

  const core =
    valuation.core_metrics
    ||
    {};

  metricsEl.innerHTML = [
    metric(
      "Basis",
      state.financial_basis
      ||
      "-"
    ),

    metric(
      "Revenue",
      fmtB(
        state.revenue
      )
    ),

    metric(
      "FCF",
      fmtB(
        state.free_cash_flow
      )
    ),

    metric(
      "Market Cap",
      fmtB(
        state.market_cap
      )
    ),

    metric(
      "P/FCF",
      fmtX(
        core.price_to_fcf
      )
    ),

    metric(
      "FCF Yield",
      fmtPct(
        core.fcf_yield
      )
    )
  ].join("");

  const scenarios =
    valuation.scenarios
    ||
    {};

  const values = [
    "bear",
    "base",
    "bull"
  ].map(
    key => ({
      name:
        key[0].toUpperCase()
        +
        key.slice(1),

      value:
        scenarios[key]
        ?.estimated_equity_value
    })
  ).filter(
    item =>
      typeof item.value
      ===
      "number"
  );

  if (values.length) {
    const maxValue =
      Math.max(
        ...values.map(
          item =>
            item.value
        ),
        state.market_cap
        ||
        0
      );

    valuationBarsEl.innerHTML =
      values.map(
        item => {
          const width =
            maxValue > 0
              ?
              Math.max(
                3,
                item.value
                /
                maxValue
                *
                100
              )
              :
              0;

          return `
            <div class="bar-row">
              <div>${item.name}</div>

              <div class="bar-track">
                <div
                  class="bar-fill"
                  style="width:${width}%"
                ></div>
              </div>

              <div>
                ${fmtB(item.value)}
              </div>
            </div>
          `;
        }
      ).join("");
  }

  const verification =
    state.deterministic_verification;

  if (
    verification
    &&
    Object.keys(
      verification
    ).length
  ) {
    verificationEl.className =
      `verification ${
        verification.passed
          ?
          "good"
          :
          "bad"
      }`;

    verificationEl.textContent =
      `Passed: ${verification.passed}\n`
      +
      `Score: ${verification.score ?? "-"}\n`
      +
      `Data failures: ${(verification.data_failures || []).length}\n`
      +
      `Math failures: ${(verification.math_failures || []).length}\n`
      +
      `Model failures: ${(verification.model_failures || []).length}\n`
      +
      `Warnings: ${(verification.warnings || []).length}`;
  }

  if (state.final_answer) {
    finalAnswerEl.textContent =
      state.final_answer;
  }
}


function resetUI() {
  timelineEl.innerHTML =
    "";

  identityCard.classList.add(
    "hidden"
  );

  metricsEl.innerHTML =
    "";

  valuationBarsEl.innerHTML =
    "";

  verificationEl.className =
    "verification empty";

  verificationEl.textContent =
    "尚未运行";

  finalAnswerEl.textContent =
    "研究进行中…";

  document.querySelectorAll(
    ".node"
  ).forEach(
    node =>
      node.className =
        "node"
  );

  currentNode =
    null;
}


async function runResearch(query) {
  resetUI();

  setStatus(
    "Running",
    "running"
  );

  runButton.disabled =
    true;

  startTime =
    performance.now();

  timer =
    setInterval(
      () => {
        elapsedEl.textContent =
          `${
            (
              (
                performance.now()
                -
                startTime
              )
              /
              1000
            ).toFixed(1)
          }s`;
      },
      100
    );

  const response =
    await fetch(
      `/api/research/stream?query=${encodeURIComponent(query)}`
    );

  if (
    !response.ok
    ||
    !response.body
  ) {
    throw new Error(
      await response.text()
      ||
      "Failed to start research"
    );
  }

  const reader =
    response.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer =
    "";

  while (true) {
    const {
      done,
      value
    } =
      await reader.read();

    if (done) {
      break;
    }

    buffer +=
      decoder.decode(
        value,
        {
          stream: true
        }
      );

    const parts =
      buffer.split(
        "\n\n"
      );

    buffer =
      parts.pop()
      ||
      "";

    for (
      const part
      of parts
    ) {
      if (
        !part.startsWith(
          "data: "
        )
      ) {
        continue;
      }

      const event =
        JSON.parse(
          part.slice(6)
        );

      if (
        event.type
        ===
        "identity"
      ) {
        setNode(
          "resolver"
        );

        showIdentity(
          event.data
        );

        addEvent(
          "Resolver",
          event.data.status
          ===
          "resolved"
            ?
            `${event.data.company_name} → ${event.data.ticker}`
            :
            event.data.status,
          event.data.status
          ===
          "resolved"
            ?
            "done"
            :
            "error"
        );
      }

      if (
        event.type
        ===
        "node"
      ) {
        setNode(
          event.node,
          "done"
        );

        addEvent(
          NODE_LABELS[
            event.node
          ]
          ||
          event.node,

          event.detail
          ||
          "completed",

          "done"
        );

        if (event.state) {
          renderResults(
            event.state
          );
        }
      }

      if (
        event.type
        ===
        "node_start"
      ) {
        setNode(
          event.node,
          "active"
        );

        addEvent(
          NODE_LABELS[
            event.node
          ]
          ||
          event.node,

          event.detail
          ||
          "running",

          "active"
        );
      }

      if (
        event.type
        ===
        "router"
      ) {
        setNode(
          "typed_router"
        );

        addEvent(
          "Typed Issue Router",
          event.detail
          ||
          "",
          "done"
        );
      }

      if (
        event.type
        ===
        "final"
      ) {
        renderResults(
          event.state
          ||
          {}
        );

        const success =
          event.state?.status
          ===
          "success";

        setStatus(
          event.state?.status
          ||
          "Done",

          success
            ?
            "success"
            :
            "failed"
        );
      }

      if (
        event.type
        ===
        "error"
      ) {
        addEvent(
          "Error",
          event.message
          ||
          "Unknown error",
          "error"
        );

        setStatus(
          "Error",
          "failed"
        );

        finalAnswerEl.textContent =
          event.message
          ||
          "Unknown error";
      }
    }
  }

  clearInterval(
    timer
  );

  runButton.disabled =
    false;
}


document.querySelector(
  "#researchForm"
).addEventListener(
  "submit",

  async event => {
    event.preventDefault();

    const query =
      document.querySelector(
        "#companyQuery"
      ).value.trim();

    if (!query) {
      return;
    }

    try {
      await runResearch(
        query
      );

    } catch (error) {
      clearInterval(
        timer
      );

      runButton.disabled =
        false;

      setStatus(
        "Error",
        "failed"
      );

      addEvent(
        "Error",
        error.message,
        "error"
      );

      finalAnswerEl.textContent =
        error.message;
    }
  }
);


renderGraph();
