import React from "react";

function fmtMoedaCurta(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `R$ ${(v / 1_000).toFixed(0)}k`;
  return `R$ ${v.toFixed(0)}`;
}

export const GraficoCashflowValeDaMorte: React.FC<{
  rotulos: string[];
  fluxoMensal: number[];
  caixaAcumulado: number[];
}> = ({ rotulos, fluxoMensal, caixaAcumulado }) => {
  if (!rotulos.length) return null;
  const W = 900;
  const H = 340;
  const padL = 72;
  const padR = 30;
  const padT = 36;
  const padB = 46;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const todosValores = [...fluxoMensal, ...caixaAcumulado, 0];
  const minVal = Math.min(...todosValores);
  const maxVal = Math.max(...todosValores);
  const span = maxVal - minVal || 1;

  const yPos = (v: number) => padT + plotH - ((v - minVal) / span) * plotH;
  const yZero = yPos(0);
  const n = rotulos.length;
  const stepX = plotW / Math.max(1, n);
  const barW = Math.max(4, stepX * 0.62);

  const pontosLinha = caixaAcumulado
    .map((val, idx) => `${padL + idx * stepX + stepX / 2},${yPos(val)}`)
    .join(" ");

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 my-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between mb-2">
        <h4 className="font-bold text-slate-900 text-sm">
          Projeção de Cashflow — Atravessia do Vale da Morte
        </h4>
        <div className="flex items-center gap-4 text-xs font-semibold">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-[#16A34A] inline-block" />
            Resultado Mensal (+)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-[#DC2626] inline-block" />
            Resultado Mensal (-)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-[#0F172A] inline-block" />
            Caixa Consolidado (Balanço)
          </span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {[0, 0.25, 0.5, 0.75, 1].map((p) => {
          const val = minVal + p * span;
          const y = yPos(val);
          return (
            <g key={p}>
              <line
                x1={padL}
                y1={y}
                x2={W - padR}
                y2={y}
                stroke="#E2E8F0"
                strokeDasharray="3 3"
              />
              <text
                x={padL - 8}
                y={y + 4}
                textAnchor="end"
                fontSize="10"
                fill="#64748B"
              >
                {fmtMoedaCurta(val)}
              </text>
            </g>
          );
        })}
        <line
          x1={padL}
          y1={yZero}
          x2={W - padR}
          y2={yZero}
          stroke="#94A3B8"
          strokeWidth="1.5"
        />
        {fluxoMensal.map((val, idx) => {
          const x = padL + idx * stepX + (stepX - barW) / 2;
          const y = val >= 0 ? yPos(val) : yZero;
          const h = Math.max(2, Math.abs(yPos(val) - yZero));
          return (
            <rect
              key={idx}
              x={x}
              y={y}
              width={barW}
              height={h}
              fill={val < 0 ? "#DC2626" : "#16A34A"}
              rx="2"
            >
              <title>{`${rotulos[idx]}: R$ ${val.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`}</title>
            </rect>
          );
        })}
        <polyline
          fill="none"
          stroke="#0F172A"
          strokeWidth="2.8"
          points={pontosLinha}
        />
        {rotulos.map((rot, idx) => {
          if (idx % Math.max(1, Math.floor(n / 10)) !== 0 && idx !== n - 1)
            return null;
          return (
            <text
              key={idx}
              x={padL + idx * stepX + stepX / 2}
              y={H - 14}
              textAnchor="middle"
              fontSize="10"
              fill="#475569"
            >
              {rot}
            </text>
          );
        })}
      </svg>
    </div>
  );
};

export const GraficoRoscaBurnRate: React.FC<{
  cogsNuvem: number;
  opexFixo: number;
  impostosGateways: number;
}> = ({ cogsNuvem, opexFixo, impostosGateways }) => {
  const total = Math.max(0.01, cogsNuvem + opexFixo + impostosGateways);
  const fatias = [
    { label: "Serviços Cloud (COGS)", valor: cogsNuvem, cor: "#2563EB" },
    { label: "Opex e Despesas Fixas", valor: opexFixo, cor: "#0F172A" },
    { label: "Impostos e Gateways", valor: impostosGateways, cor: "#94A3B8" },
  ];

  const R = 70;
  const C = 2 * Math.PI * R;
  let offsetAcumulado = 0;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col items-center">
      <div className="flex items-center gap-6 my-2">
        <svg width="180" height="180" viewBox="0 0 180 180">
          {fatias.map((f, i) => {
            const pct = f.valor / total;
            const dash = pct * C;
            const strokeDashoffset = -offsetAcumulado;
            offsetAcumulado += dash;
            return (
              <circle
                key={i}
                cx="90"
                cy="90"
                r={R}
                fill="transparent"
                stroke={f.cor}
                strokeWidth="26"
                strokeDasharray={`${dash} ${C - dash}`}
                strokeDashoffset={strokeDashoffset}
                transform="rotate(-90 90 90)"
              />
            );
          })}
          <text
            x="90"
            y="86"
            textAnchor="middle"
            fontSize="11"
            fontWeight="bold"
            fill="#64748B"
          >
            Burn Total
          </text>
          <text
            x="90"
            y="104"
            textAnchor="middle"
            fontSize="12"
            fontWeight="800"
            fill="#0F172A"
          >
            {fmtMoedaCurta(cogsNuvem + opexFixo + impostosGateways)}
          </text>
        </svg>
        <div className="space-y-2 text-xs">
          {fatias.map((f, i) => (
            <div key={i} className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-sm inline-block"
                style={{ backgroundColor: f.cor }}
              />
              <div>
                <div className="font-bold text-slate-800">{f.label}</div>
                <div className="text-slate-500">
                  R$ {f.valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })} (
                  {((f.valor / total) * 100).toFixed(1)}%)
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const GraficoMRRTracao: React.FC<{
  rotulos: string[];
  mrrMensal: number[];
  usuariosPagantes: number[];
}> = ({ rotulos, mrrMensal, usuariosPagantes }) => {
  const rots = rotulos.slice(1);
  const mrr = mrrMensal.slice(1);
  const users = usuariosPagantes.slice(1);
  if (!rots.length) return null;

  const W = 520;
  const H = 220;
  const padL = 58;
  const padR = 48;
  const padT = 24;
  const padB = 32;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const maxMrr = Math.max(...mrr, 1);
  const maxUsers = Math.max(...users, 1);
  const n = rots.length;
  const stepX = plotW / Math.max(1, n - 1);

  const ptsMrr = mrr
    .map((v, i) => `${padL + i * stepX},${padT + plotH - (v / maxMrr) * plotH}`)
    .join(" ");
  const ptsUsers = users
    .map(
      (v, i) => `${padL + i * stepX},${padT + plotH - (v / maxUsers) * plotH}`
    )
    .join(" ");

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between text-xs font-semibold mb-2">
        <span className="text-[#2563EB]">━ Evolução do MRR (R$)</span>
        <span className="text-[#16A34A]">┅ Expansão da Base Paga (Clientes)</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {[0, 0.5, 1].map((p) => {
          const y = padT + plotH - p * plotH;
          return (
            <g key={p}>
              <line
                x1={padL}
                y1={y}
                x2={W - padR}
                y2={y}
                stroke="#E2E8F0"
                strokeDasharray="3 3"
              />
              <text
                x={padL - 6}
                y={y + 4}
                textAnchor="end"
                fontSize="9"
                fill="#2563EB"
              >
                {fmtMoedaCurta(p * maxMrr)}
              </text>
              <text
                x={W - padR + 6}
                y={y + 4}
                textAnchor="start"
                fontSize="9"
                fill="#16A34A"
              >
                {Math.round(p * maxUsers)}
              </text>
            </g>
          );
        })}
        <polyline
          fill="none"
          stroke="#2563EB"
          strokeWidth="2.8"
          points={ptsMrr}
        />
        <polyline
          fill="none"
          stroke="#16A34A"
          strokeWidth="2.2"
          strokeDasharray="4 4"
          points={ptsUsers}
        />
      </svg>
    </div>
  );
};
