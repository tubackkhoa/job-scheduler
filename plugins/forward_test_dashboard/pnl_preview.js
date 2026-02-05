var ae = Object.create;
var Mt = Object.defineProperty;
var re = Object.getOwnPropertyDescriptor;
var se = Object.getOwnPropertyNames;
var le = Object.getPrototypeOf,
  ce = Object.prototype.hasOwnProperty;
var Bt = (e, o) => () => (o || e((o = { exports: {} }).exports, o), o.exports);
var de = (e, o, i, a) => {
  if ((o && typeof o == 'object') || typeof o == 'function')
    for (let s of se(o))
      !ce.call(e, s) &&
        s !== i &&
        Mt(e, s, {
          get: () => o[s],
          enumerable: !(a = re(o, s)) || a.enumerable,
        });
  return e;
};
var yt = (e, o, i) => (
  (i = e != null ? ae(le(e)) : {}),
  de(
    o || !e || !e.__esModule
      ? Mt(i, 'default', { value: e, enumerable: !0 })
      : i,
    e
  )
);
var Nt = Bt((ht) => {
  'use strict';
  var ue = Symbol.for('react.transitional.element'),
    ge = Symbol.for('react.fragment');
  function Ft(e, o, i) {
    var a = null;
    if (
      (i !== void 0 && (a = '' + i),
      o.key !== void 0 && (a = '' + o.key),
      'key' in o)
    ) {
      i = {};
      for (var s in o) s !== 'key' && (i[s] = o[s]);
    } else i = o;
    return (
      (o = i.ref),
      { $$typeof: ue, type: e, key: a, ref: o !== void 0 ? o : null, props: i }
    );
  }
  ht.Fragment = ge;
  ht.jsx = Ft;
  ht.jsxs = Ft;
});
var st = Bt((on, zt) => {
  'use strict';
  zt.exports = Nt();
});
var r = yt(st(), 1),
  { useState: E, useEffect: pe } = React,
  {
    Dialog: fe,
    DialogTitle: me,
    DialogContent: ye,
    DialogActions: he,
    Button: lt,
    Stack: ct,
    Typography: bt,
    CircularProgress: be,
    Alert: Ot,
    Tabs: Ce,
    Tab: Ut,
    Box: Rt,
    TextField: jt,
    Switch: ve,
    FormControlLabel: Te,
    Chip: xe,
  } = Mui,
  { Storefront: Pe, Work: Se, CheckCircle: $t } = MuiIcon,
  { ConfigForm: ke } = Components,
  { SESSIONS: Wt } = Constants,
  { buildJinjaContext: wt } = Utils,
  nt = 'alpha_miner.plugins.LiveTradeForUserPlugin',
  It = Wt[1].id,
  De = 'production',
  Et = { env: De, url: null, apikey: null };
function Ht(e) {
  let { children: o, value: i, index: a, ...s } = e;
  return (0, r.jsx)('div', {
    role: 'tabpanel',
    hidden: i !== a,
    ...s,
    children: i === a && (0, r.jsx)(Rt, { sx: { pt: 3 }, children: o }),
  });
}
function Jt({ open: e, onClose: o, modelIdentity: i }) {
  let [a, s] = E(!1),
    [C, c] = E(null),
    [l, f] = E(0),
    [P, m] = E(null),
    [y, S] = E(null),
    [N, v] = E(null),
    [h, z] = E(null),
    [_, G] = E({}),
    [g, H] = E(!1),
    [O, V] = E(!1),
    [q, w] = E(!1),
    [R, b] = E(!1),
    [Q, Y] = E(''),
    [L, U] = E('');
  pe(() => {
    e && i && (z(null), w(!1), X(), A());
  }, [e, i]);
  let X = async () => {
      (s(!0), c(null));
      try {
        let d = await api.fetchPlugins(),
          I = d.find(($) => $.package === nt);
        if (!I)
          throw new Error(
            `Plugin ${nt} not found. Available plugins: ${d.map(($) => $.package).join(', ')}`
          );
        m(I.id);
        let W = It,
          M = await api.fetchSchema(W, I.id),
          { schema: j, globals: mt, jobs: J } = M;
        S(j);
        let kt = Object.fromEntries(
          Object.entries(j.properties).map(([$, at]) => [$, at.default])
        );
        if (
          (v(await Utils.getEnvDoc(mt || {})),
          G({ ...kt, model_key: i, model_tag: 'production' }),
          J && Array.isArray(J))
        ) {
          let $ = J.find((at) => at.config?.model_key === i);
          $ && z($);
        }
      } catch (d) {
        c(d.message);
      } finally {
        s(!1);
      }
    },
    A = async () => {
      try {
        let I = await wt(
            nt,
            {},
            !0
          )('{{ list_trade_models(env, url, apikey) }}', Et),
          W = (typeof I == 'string' ? JSON.parse(I.replace(/'/g, '"')) : I)
            .versions,
          M = Array.isArray(W) ? W.some((j) => j.id === i) : !1;
        w(M);
      } catch (d) {
        (console.error('Error checking registration status:', d), w(!1));
      }
    },
    ft = async () => {
      (b(!0), c(null));
      try {
        (await wt(
          nt,
          {},
          !0
        )('{{ create_trade_model(payload, url, apikey, env) }}', {
          payload: { key: i, name: Q || void 0, description: L || void 0 },
          ...Et,
        }),
          w(!0),
          await X());
      } catch (d) {
        c(d.message || 'Failed to register model');
      } finally {
        b(!1);
      }
    },
    xt = async () => {
      (b(!0), c(null));
      try {
        (await wt(
          nt,
          {},
          !0
        )('{{ deactivate_trade_model(key, url, apikey, env) }}', {
          key: i,
          ...Et,
        }),
          w(!1));
      } catch (d) {
        c(d.message || 'Failed to unsubscribe model');
      } finally {
        b(!1);
      }
    },
    Pt = async () => {
      if (P) {
        (H(!0), c(null));
        try {
          let d = It,
            W = {
              config: Object.fromEntries(
                Object.entries(_).filter(([M, j]) => j !== void 0)
              ),
              description: `Live Trading for ${i}`,
              pluginId: P,
              sessionId: d,
            };
          (await api.updateConfig(0, W), X());
        } catch (d) {
          c(d.message);
        } finally {
          H(!1);
        }
      }
    },
    St = async () => {
      if (h) {
        (V(!0), c(null));
        try {
          let d = !h.active;
          (await api.activateJob(h.id, d), z({ ...h, active: d ? 1 : 0 }));
        } catch (d) {
          c(d.message || 'Failed to toggle job status');
        } finally {
          V(!1);
        }
      }
    };
  return (0, r.jsxs)(fe, {
    open: e,
    onClose: o,
    maxWidth: 'lg',
    fullWidth: !0,
    children: [
      (0, r.jsxs)(me, { children: ['Publish Model: ', i] }),
      (0, r.jsxs)(ye, {
        dividers: !0,
        children: [
          C &&
            (0, r.jsx)(Ot, { severity: 'error', sx: { mb: 2 }, children: C }),
          a
            ? (0, r.jsx)(Rt, {
                display: 'flex',
                justifyContent: 'center',
                p: 4,
                children: (0, r.jsx)(be, {}),
              })
            : (0, r.jsxs)(Rt, {
                children: [
                  (0, r.jsxs)(Ce, {
                    value: l,
                    onChange: (d, I) => f(I),
                    sx: { borderBottom: 1, borderColor: 'divider', mb: 2 },
                    children: [
                      (0, r.jsx)(Ut, {
                        icon: (0, r.jsx)(Pe, {}),
                        iconPosition: 'start',
                        label: 'Marketplace',
                      }),
                      (0, r.jsx)(Ut, {
                        icon: (0, r.jsx)(Se, {}),
                        iconPosition: 'start',
                        label: 'Production Job',
                      }),
                    ],
                  }),
                  (0, r.jsx)(Ht, {
                    value: l,
                    index: 0,
                    children: (0, r.jsxs)(ct, {
                      spacing: 3,
                      alignItems: 'center',
                      py: 4,
                      children: [
                        (0, r.jsxs)(bt, {
                          variant: 'h6',
                          children: [
                            'Marketplace Status:',
                            ' ',
                            q ? 'Registered' : 'Not Registered',
                          ],
                        }),
                        q
                          ? (0, r.jsx)(lt, {
                              variant: 'outlined',
                              color: 'error',
                              onClick: xt,
                              disabled: R,
                              children: 'Unsubscribe Model',
                            })
                          : (0, r.jsxs)(ct, {
                              spacing: 2,
                              width: '100%',
                              maxWidth: 400,
                              children: [
                                (0, r.jsx)(jt, {
                                  fullWidth: !0,
                                  label: 'Model Name (Optional)',
                                  value: Q,
                                  onChange: (d) => Y(d.target.value),
                                  placeholder:
                                    'Enter a display name for your model',
                                  disabled: R,
                                }),
                                (0, r.jsx)(jt, {
                                  fullWidth: !0,
                                  label: 'Description (Optional)',
                                  value: L,
                                  onChange: (d) => U(d.target.value),
                                  placeholder: "Describe your model's strategy",
                                  multiline: !0,
                                  rows: 3,
                                  disabled: R,
                                }),
                                (0, r.jsx)(lt, {
                                  variant: 'contained',
                                  color: 'primary',
                                  startIcon: (0, r.jsx)($t, {}),
                                  onClick: ft,
                                  disabled: R,
                                  children: 'Register Model',
                                }),
                              ],
                            }),
                        (0, r.jsx)(bt, {
                          variant: 'body2',
                          color: 'text.secondary',
                          children:
                            "Registering allows other users to subscribe to this model's signals.",
                        }),
                      ],
                    }),
                  }),
                  (0, r.jsx)(Ht, {
                    value: l,
                    index: 1,
                    children: h
                      ? (0, r.jsxs)(ct, {
                          spacing: 2,
                          alignItems: 'center',
                          py: 4,
                          children: [
                            (0, r.jsx)($t, {
                              color: 'success',
                              sx: { fontSize: 48 },
                            }),
                            (0, r.jsx)(bt, {
                              variant: 'h6',
                              children: 'Production Job Found',
                            }),
                            (0, r.jsxs)(bt, { children: ['Job ID: ', h.id] }),
                            (0, r.jsxs)(ct, {
                              direction: 'row',
                              spacing: 2,
                              alignItems: 'center',
                              children: [
                                (0, r.jsx)(xe, {
                                  label: h.active ? 'Active' : 'Inactive',
                                  color: h.active ? 'success' : 'default',
                                  size: 'medium',
                                }),
                                (0, r.jsx)(Te, {
                                  control: (0, r.jsx)(ve, {
                                    checked: !!h.active,
                                    onChange: St,
                                    disabled: O,
                                  }),
                                  label: 'Active',
                                }),
                              ],
                            }),
                            (0, r.jsx)(lt, {
                              variant: 'outlined',
                              onClick: () =>
                                window.open(
                                  `/plugins/${P}/sessions/${It}/jobs/${h.id}`,
                                  '_blank'
                                ),
                              children: 'View Job Details',
                            }),
                          ],
                        })
                      : (0, r.jsxs)(ct, {
                          spacing: 2,
                          children: [
                            (0, r.jsx)(Ot, {
                              severity: 'info',
                              children:
                                'No production job found. Configure settings below to create one.',
                            }),
                            y &&
                              (0, r.jsx)(ke, {
                                pluginId: P,
                                pluginPackage: nt,
                                sessionId: Wt[1].id,
                                schema: y,
                                formData: _,
                                onChange: G,
                                env: N,
                              }),
                            (0, r.jsx)(lt, {
                              variant: 'contained',
                              color: 'success',
                              onClick: Pt,
                              disabled: g,
                              children: g
                                ? 'Creating...'
                                : 'Create Production Job',
                            }),
                          ],
                        }),
                  }),
                ],
              }),
        ],
      }),
      (0, r.jsx)(he, {
        children: (0, r.jsx)(lt, { onClick: o, children: 'Close' }),
      }),
    ],
  });
}
var t = yt(st(), 1),
  {
    useCallback: we,
    useEffect: ot,
    useMemo: dt,
    useRef: Gt,
    useState: p,
  } = React,
  {
    createChart: Ie,
    IChartApi: rn,
    LineData: sn,
    LineSeries: Vt,
    MouseEventParams: ln,
    UTCTimestamp: cn,
  } = LightweightChart,
  {
    ViewColumn: Ee,
    FilterList: Re,
    Clear: qt,
    Settings: Le,
    ShowChart: _e,
    Storefront: Ae,
  } = MuiIcon,
  {
    Table: Me,
    TableBody: Be,
    TableCell: tt,
    TableContainer: Fe,
    TableHead: Ne,
    TableRow: Lt,
    TableSortLabel: ze,
    TablePagination: Oe,
    TextField: pt,
    Box: D,
    Checkbox: Ue,
    FormControlLabel: je,
    Stack: At,
    IconButton: ut,
    Button: it,
    Card: Ct,
    CardContent: vt,
    Typography: x,
    Grid: et,
    Popover: $e,
    Paper: He,
    MenuItem: _t,
    Dialog: Zt,
    DialogTitle: Qt,
    DialogContent: Kt,
    DialogActions: te,
    CircularProgress: We,
  } = Mui,
  F = {
    positive: '#28a745',
    negative: '#dc3545',
    neutral: '#6c757d',
    warning: '#ffc107',
  };
function Z(e, o, i = !1) {
  return `<span style="color:${o};${i ? 'font-weight:bold;' : ''}">${e}</span>`;
}
function gt(e) {
  return e == null
    ? '-'
    : e > 0
      ? Z(`\u2197 +$${e.toFixed(4)}`, F.positive, !0)
      : e < 0
        ? Z(`\u2198 $${e.toFixed(4)}`, F.negative, !0)
        : Z('$0.0000', F.neutral);
}
function Je(e) {
  return e
    ? e.state === 'active'
      ? Z(`\u2713 Active (${e.label})`, F.positive)
      : e.state === 'inactive'
        ? Z(`\u23F8 Inactive (${e.label})`, F.warning)
        : Z('\u2298 No Job', F.neutral)
    : '-';
}
function Ge(e) {
  if (!e) return '-';
  let o =
    e.direction === 'BUY' || e.direction === 'LONG' ? F.positive : F.negative;
  return `${Z(e.symbol, o, !0)} ${gt(e.pnl)}`;
}
function Ve(e) {
  if (e == null) return '-';
  let o = e * 100,
    i = F.negative;
  return (
    o >= 50 ? (i = F.positive) : o >= 40 && (i = F.neutral),
    Z(`${o.toFixed(1)}%`, i, !0)
  );
}
function qe(e) {
  if (!e) return '-';
  let o = new Date(e);
  if (isNaN(o.getTime())) return '-';
  let i = o.getUTCFullYear(),
    a = String(o.getUTCMonth() + 1).padStart(2, '0'),
    s = String(o.getUTCDate()).padStart(2, '0'),
    C = String(o.getUTCHours()).padStart(2, '0'),
    c = String(o.getUTCMinutes()).padStart(2, '0');
  return `${i}-${a}-${s} ${C}:${c} UTC`;
}
function Ye(e, o) {
  if (!e?.length)
    return {
      rows: [],
      totals: { total_models: 0, total_pnl: 0, total_positions: 0 },
    };
  let i = {};
  for (let l of e) {
    let f = l.identity;
    f && (i[f] = l);
  }
  e = Object.values(i);
  let a = {};
  for (let l of o) {
    let f = l?.config?.model_key;
    f &&
      (a[f] = {
        state: l.active ? 'active' : 'inactive',
        label: l.description || 'No description',
        job: l,
      });
  }
  let s = [],
    C = 0,
    c = 0;
  for (let l of e) {
    let f = l.identity;
    if (!f) continue;
    let P = l.totalPnl ?? 0,
      m = Number(l.totalPositions ?? 0);
    ((C += P), (c += m));
    let y = l.lastPosition,
      S = y
        ? { symbol: y.symbol ?? '', direction: y.side ?? '', pnl: y.pnl ?? 0 }
        : null,
      N = y?.time ?? null,
      v = a[f];
    s.push({
      Identity: f,
      Model: l.modelName,
      'Total PNL': gt(P),
      'PNL 1H': gt(l.pnlDelta1h ?? 0),
      'PNL 4H': gt(l.pnlDelta4h ?? 0),
      'PNL 1D': gt(l.pnlDelta1d ?? 0),
      Winrate: Ve(l.winrate),
      'Max Drawdown': l.maxDrawdown,
      'Latest Position': Ge(S),
      'Latest Position Time': N,
      Status: Je(v),
      'Hide Status': v?.state ?? '',
      'Hide Job': v?.job,
      Started: qe(l.startedAt ?? ''),
      'Total Positions': m,
      'Total Runtime': l.totalRunningTime ?? '-',
    });
  }
  return {
    rows: s,
    totals: { total_models: s.length, total_pnl: C, total_positions: c },
  };
}
function Yt(e) {
  return e
    ? new Date(e).toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
    : '';
}
var Xe = React.memo(({ visible: e, x: o, y: i, data: a }) =>
  !e || !a
    ? null
    : (0, t.jsxs)(D, {
        sx: {
          position: 'absolute',
          left: o,
          top: i,
          bgcolor: 'rgba(0,0,0,0.85)',
          color: '#fff',
          px: 1.5,
          py: 1,
          borderRadius: 1,
          fontSize: 12,
          pointerEvents: 'none',
          zIndex: 10,
          minWidth: 220,
          boxShadow: 3,
        },
        children: [
          (0, t.jsxs)(x, {
            variant: 'caption',
            display: 'block',
            children: [
              (0, t.jsx)('strong', { children: 'Open time:' }),
              ' ',
              a.openTime,
            ],
          }),
          (0, t.jsxs)(x, {
            variant: 'caption',
            display: 'block',
            children: [
              (0, t.jsx)('strong', { children: 'Close time:' }),
              ' ',
              a.time,
            ],
          }),
          (0, t.jsxs)(x, {
            variant: 'caption',
            display: 'block',
            children: [
              (0, t.jsx)('strong', { children: 'Symbol:' }),
              ' ',
              a.symbol,
              ' | ',
              (0, t.jsx)('strong', { children: 'Side:' }),
              ' ',
              (0, t.jsx)(D, {
                component: 'span',
                sx: {
                  color: a.side === 'BUY' ? '#4caf50' : '#f44336',
                  fontWeight: 600,
                },
                children: a.side,
              }),
            ],
          }),
          (0, t.jsx)(D, {
            sx: { my: 0.5, borderTop: '1px solid rgba(255,255,255,0.2)' },
          }),
          (0, t.jsxs)(x, {
            variant: 'caption',
            display: 'block',
            children: [
              (0, t.jsx)('strong', { children: 'PnL:' }),
              ' ',
              (0, t.jsxs)(D, {
                component: 'span',
                sx: {
                  color: a.pnl >= 0 ? '#4caf50' : '#f44336',
                  fontWeight: 600,
                },
                children: [a.pnl >= 0 ? '+' : '', a.pnl.toFixed(4)],
              }),
            ],
          }),
          (0, t.jsxs)(x, {
            variant: 'caption',
            display: 'block',
            children: [
              (0, t.jsx)('strong', { children: 'Accumulated:' }),
              ' ',
              (0, t.jsxs)(D, {
                component: 'span',
                sx: {
                  color: a.accumulatedPnl >= 0 ? '#2962FF' : '#f44336',
                  fontWeight: 600,
                },
                children: [
                  a.accumulatedPnl >= 0 ? '+' : '',
                  a.accumulatedPnl.toFixed(4),
                ],
              }),
            ],
          }),
        ],
      })
);
function Tt(e) {
  if (typeof e == 'number') return e;
  if (typeof e == 'string') {
    let i = e.replace(/<[^>]*>/g, '').replace(/[^\d.-]/g, ''),
      a = parseFloat(i);
    return isNaN(a) ? 0 : a;
  }
  return 0;
}
function Xt(e, o, i) {
  let a = e[i],
    s = o[i];
  if (
    typeof a == 'string' &&
    typeof s == 'string' &&
    /^\d{4}-\d{2}-\d{2}T/.test(a) &&
    /^\d{4}-\d{2}-\d{2}T/.test(s)
  ) {
    let P = Date.parse(a),
      m = Date.parse(s);
    if (!isNaN(P) && !isNaN(m)) return m < P ? -1 : m > P ? 1 : 0;
  }
  let C = Tt(a),
    c = Tt(s);
  if (C !== c) return C < c ? 1 : -1;
  let l = String(a ?? '').toLowerCase(),
    f = String(s ?? '').toLowerCase();
  return f < l ? -1 : f > l ? 1 : 0;
}
function Ze(e, o) {
  return e === 'desc' ? (i, a) => Xt(i, a, o) : (i, a) => -Xt(i, a, o);
}
var Qe = [
    'num_session',
    'num_signal',
    'signal_direction',
    'sl_percent',
    'total_volume',
    'tp_percent',
    'volatility',
  ],
  Ke = ({
    open: e,
    onClose: o,
    editingRow: i,
    initialValues: a,
    onSave: s,
    saving: C,
  }) => {
    if (!i) return null;
    let [c, l] = p(a || {});
    ot(() => {
      l(a || {});
    }, [a, e]);
    let f = (m, y) => {
        l((S) => ({ ...S, [m]: y }));
      },
      P = () => {
        s(c);
      };
    return (0, t.jsxs)(Zt, {
      open: e,
      onClose: o,
      maxWidth: 'sm',
      fullWidth: !0,
      children: [
        (0, t.jsxs)(Qt, {
          children: ['Edit Config: ', i.Identity || 'Unknown'],
        }),
        (0, t.jsx)(Kt, {
          dividers: !0,
          children: (0, t.jsx)(et, {
            container: !0,
            spacing: 2,
            sx: { pt: 1 },
            children: Qe.map((m) => {
              let y = c[m],
                S = typeof y == 'number';
              return (0, t.jsx)(
                et,
                {
                  size: { sm: 6 },
                  children: (0, t.jsx)(pt, {
                    fullWidth: !0,
                    size: 'small',
                    label: m,
                    value: y ?? '',
                    type: S ? 'number' : 'text',
                    onChange: (N) => {
                      let v = S ? parseFloat(N.target.value) : N.target.value;
                      f(m, v);
                    },
                  }),
                },
                m
              );
            }),
          }),
        }),
        (0, t.jsxs)(te, {
          children: [
            (0, t.jsx)(it, {
              onClick: o,
              disabled: C,
              color: 'inherit',
              children: 'Cancel',
            }),
            (0, t.jsx)(it, {
              onClick: P,
              disabled: C,
              variant: 'contained',
              children: C ? 'Saving...' : 'Save Changes',
            }),
          ],
        }),
      ],
    });
  },
  tn = ({ open: e, onClose: o, row: i, registry: a }) => {
    let [s, C] = p(!1),
      [c, l] = p(),
      [f, P] = p(null),
      [m, y] = p(''),
      [S, N] = p(''),
      v = Gt(null),
      h = Gt(null),
      [z, _] = p({ visible: !1, x: 0, y: 0 }),
      G = we(async () => {
        if (i) {
          (C(!0), P(null));
          try {
            let g = Utils.buildJinjaContext(
                a.formContext.pluginPackage,
                a.formContext.formData
              ),
              H = i.Identity || i.id,
              O = (R) => (R ? `${R}:00Z` : ''),
              V = O(m),
              q = O(S),
              w = await g(
                '{{ get_equity_curve_forward_test(identity, startTime, endTime) }}',
                { identity: H, startTime: V, endTime: q }
              );
            w && Array.isArray(w) ? l(w) : l([]);
          } catch (g) {
            (console.error('Failed to fetch equity curve', g),
              P('Failed to load chart data: ' + g.message),
              l([]));
          } finally {
            C(!1);
          }
        }
      }, [i, m, S, Utils, a]);
    return (
      ot(() => {
        e || _((g) => ({ ...g, visible: !1 }));
      }, [e]),
      ot(() => {
        e && i && G();
      }, [e, i, G]),
      ot(() => {
        if (!e || !v.current || !c) return;
        (h.current?.remove(), (h.current = null));
        let g = Ie(v.current, {
          width: v.current.clientWidth,
          height: 500,
          layout: { background: { color: '#ffffff' }, textColor: '#333' },
          grid: {
            vertLines: { color: '#e1e8ed' },
            horzLines: { color: '#e1e8ed' },
          },
          crosshair: {
            mode: 1,
            vertLine: { width: 1, color: '#758696', style: 3 },
            horzLine: { width: 1, color: '#758696', style: 3 },
          },
          timeScale: {
            timeVisible: !0,
            secondsVisible: !1,
            borderColor: '#d1d4dc',
          },
          rightPriceScale: { borderColor: '#d1d4dc' },
        });
        h.current = g;
        let H = g.addSeries(Vt, {
            color: '#FF6B00',
            lineWidth: 2,
            title: 'PnL',
          }),
          O = g.addSeries(Vt, {
            color: '#2962FF',
            lineWidth: 2,
            title: 'Accumulated PnL',
          }),
          V = c.map((b) => ({
            time: new Date(b.time).getTime() / 1e3,
            value: b.pnl,
          })),
          q = c.map((b) => ({
            time: new Date(b.time).getTime() / 1e3,
            value: b.accumulatedPnl,
          }));
        (H.setData(V), O.setData(q), g.timeScale().fitContent());
        let w = Utils._.throttle((b) => {
          if (!b?.time || !b?.point) {
            _((A) => ({ ...A, visible: !1 }));
            return;
          }
          if (b.point.x < 0 || b.point.y < 0) {
            _((A) => ({ ...A, visible: !1 }));
            return;
          }
          let Q = b.seriesData.get(O);
          if (!Q) {
            _((A) => ({ ...A, visible: !1 }));
            return;
          }
          let Y = Q.time * 1e3,
            L = c.find((A) => Math.abs(new Date(A.time).getTime() - Y) < 1e3);
          if (!L) return;
          let U = v.current.clientWidth - 240,
            X = v.current.clientHeight - 120;
          _({
            visible: !0,
            x: Math.min(b.point.x + 15, U),
            y: Math.min(b.point.y + 15, X),
            data: {
              time: Yt(L.time),
              openTime: Yt(L.openTime),
              symbol: L.symbol,
              side: L.side,
              pnl: L.pnl,
              accumulatedPnl: L.accumulatedPnl,
            },
          });
        }, 40);
        g.subscribeCrosshairMove(w);
        let R = () => {
          !h.current ||
            !v.current ||
            h.current.applyOptions({ width: v.current.clientWidth });
        };
        return (
          window.addEventListener('resize', R),
          () => {
            (window.removeEventListener('resize', R),
              g.unsubscribeCrosshairMove(w),
              g.remove(),
              (h.current = null));
          }
        );
      }, [c, e]),
      (0, t.jsxs)(Zt, {
        open: e,
        onClose: o,
        maxWidth: 'xl',
        fullWidth: !0,
        children: [
          (0, t.jsxs)(Qt, {
            children: ['Equity Curve: ', i?.Identity || 'Unknown'],
          }),
          (0, t.jsxs)(Kt, {
            children: [
              (0, t.jsxs)(At, {
                direction: 'row',
                spacing: 2,
                sx: { mb: 2, mt: 1 },
                children: [
                  (0, t.jsx)(pt, {
                    label: 'Start Time',
                    type: 'datetime-local',
                    value: m,
                    onChange: (g) => y(g.target.value),
                    size: 'small',
                    InputLabelProps: { shrink: !0 },
                    sx: { flex: 1 },
                  }),
                  (0, t.jsx)(pt, {
                    label: 'End Time',
                    type: 'datetime-local',
                    value: S,
                    onChange: (g) => N(g.target.value),
                    size: 'small',
                    InputLabelProps: { shrink: !0 },
                    sx: { flex: 1 },
                  }),
                  (0, t.jsx)(it, {
                    variant: 'contained',
                    onClick: G,
                    disabled: s,
                    sx: { height: 40, alignSelf: 'flex-start' },
                    children: 'Refresh',
                  }),
                ],
              }),
              (0, t.jsxs)(D, {
                sx: {
                  display: 'flex',
                  gap: 3,
                  mb: 2,
                  justifyContent: 'center',
                },
                children: [
                  (0, t.jsxs)(D, {
                    sx: { display: 'flex', alignItems: 'center', gap: 1 },
                    children: [
                      (0, t.jsx)(D, {
                        sx: {
                          width: 20,
                          height: 3,
                          bgcolor: '#FF6B00',
                          borderRadius: 1,
                        },
                      }),
                      (0, t.jsx)(x, {
                        variant: 'body2',
                        children: 'PnL (Individual Trade)',
                      }),
                    ],
                  }),
                  (0, t.jsxs)(D, {
                    sx: { display: 'flex', alignItems: 'center', gap: 1 },
                    children: [
                      (0, t.jsx)(D, {
                        sx: {
                          width: 20,
                          height: 3,
                          bgcolor: '#2962FF',
                          borderRadius: 1,
                        },
                      }),
                      (0, t.jsx)(x, {
                        variant: 'body2',
                        children: 'Accumulated PnL',
                      }),
                    ],
                  }),
                ],
              }),
              s &&
                (0, t.jsx)(D, {
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  minHeight: 400,
                  children: (0, t.jsx)(We, {}),
                }),
              f &&
                (0, t.jsx)(D, {
                  minHeight: 400,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  children: (0, t.jsx)(x, { color: 'error', children: f }),
                }),
              c &&
                (c.length
                  ? (0, t.jsx)(D, {
                      ref: v,
                      sx: {
                        position: 'relative',
                        width: '100%',
                        height: 540,
                        mt: 2,
                      },
                      children: (0, t.jsx)(Xe, { ...z }),
                    })
                  : (0, t.jsx)(D, {
                      minHeight: 400,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      children: (0, t.jsx)(x, {
                        color: 'text.secondary',
                        children: 'No data available',
                      }),
                    })),
            ],
          }),
          (0, t.jsx)(te, {
            children: (0, t.jsx)(it, {
              variant: 'contained',
              color: 'warning',
              onClick: o,
              children: 'Close',
            }),
          }),
        ],
      })
    );
  },
  un = ({ formData: e, registry: o }) => {
    let [i, a] = p('desc'),
      [s, C] = p(''),
      [c, l] = p(''),
      [f, P] = p('All'),
      [m, y] = p(0),
      [S, N] = p(10),
      [v, h] = p(null),
      [z, _] = p(null),
      [G, g] = p(!1),
      [H, O] = p(!1),
      [V, q] = p({}),
      [w, R] = p(!1),
      [b, Q] = p(null),
      [Y, L] = p({}),
      [U, X] = p([]),
      [A, ft] = p(!1),
      [xt, Pt] = p(null),
      St = (n) => {
        (Pt({ identity: n.Identity }), ft(!0));
      };
    ot(() => {
      if (e)
        try {
          let {
              models: n,
              jobList: u,
              stats: T,
            } = Utils.convertByType(e, 'object'),
            { rows: k } = Ye(T, u),
            rt = Object.fromEntries(
              n.map((K) => [K.identity, K.currentConfig])
            ),
            B = k.map((K) => ({ ...K, 'Hide currentConfig': rt[K.Identity] }));
          X(B);
        } catch (n) {
          console.error(n);
        }
    }, [e]);
    let d = dt(
        () =>
          U.length === 0
            ? []
            : Object.keys(U[0]).filter(
                (n) => !n.includes('Hide') && n !== 'config'
              ),
        [U]
      ),
      [I, W] = p({});
    ot(() => {
      d.length > 0 &&
        W((n) => {
          let u = { ...n },
            T = !1;
          return (
            d.forEach((k) => {
              u[k] === void 0 && ((u[k] = !0), (T = !0));
            }),
            T ? u : n
          );
        });
    }, [d]);
    let M = dt(() => {
        if (!U) return [];
        let n = U;
        if (((n = n.filter((u) => !Y[u.Identity || u.id])), c)) {
          let u = c.toLowerCase();
          n = n.filter((T) =>
            Object.values(T).some((k) => String(k).toLowerCase().includes(u))
          );
        }
        return (
          f !== 'All' &&
            (n = n.filter((u) => {
              let T = String(u['Hide Status']).toLowerCase();
              return T ? T === f : !1;
            })),
          n
        );
      }, [U, c, Y, f]),
      j = dt(() => (s ? [...M].sort(Ze(i, s)) : M), [M, i, s]),
      mt = dt(() => {
        let n = m * S;
        return j.slice(n, n + S);
      }, [j, m, S]),
      J = dt(() => {
        let n = M.length,
          u = 0,
          T = 0;
        return (
          M.forEach((k) => {
            ((u += Tt(k['Total PNL'])), (T += Tt(k['Total Positions'])));
          }),
          { totalModels: n, totalPnl: u, totalPositions: T }
        );
      }, [M]),
      kt = (n) => {
        (a(s === n && i === 'asc' ? 'desc' : 'asc'), C(n));
      },
      $ = (n) => {
        W((u) => ({ ...u, [n]: !u[n] }));
      },
      at = (n) => {
        let u = n.Identity || JSON.stringify(n);
        L((T) => ({ ...T, [u]: !0 }));
      },
      ee = (n) => {
        _(n);
        let u = n['Hide currentConfig'] || n.config || {};
        (q(u.config), g(!0));
      },
      ne = (n) => {
        (Q(n), R(!0));
      },
      oe = async (n) => {
        if (!(!z || !o)) {
          O(!0);
          try {
            let u = Utils.buildJinjaContext(
                o.formContext.pluginPackage,
                o.formContext.formData
              ),
              T = { ...n },
              k = z.Identity;
            (await u(
              '{{ update_model_config(webhook_url, webhook_api_key,identity, payload) }}',
              { identity: k, payload: T }
            ),
              X((rt) =>
                rt.map((B) => {
                  let K = B.Identity,
                    ie = z.Identity;
                  if (K === ie) {
                    if (B['Hide currentConfig'])
                      return {
                        ...B,
                        'Hide currentConfig': {
                          ...B['Hide currentConfig'],
                          config: { ...B['Hide currentConfig'].config, ...n },
                        },
                      };
                    if (B.config)
                      return { ...B, config: { ...B.config, ...n } };
                  }
                  return B;
                })
              ),
              g(!1),
              _(null),
              alert('Update config completed'));
          } catch (u) {
            (console.error('Failed to update config', u),
              alert('Failed to update config: ' + u.message));
          } finally {
            O(!1);
          }
        }
      },
      Dt = d.filter((n) => I[n]);
    return (0, t.jsxs)(D, {
      children: [
        (0, t.jsxs)(et, {
          container: !0,
          spacing: 2,
          sx: { mb: 2 },
          children: [
            (0, t.jsx)(et, {
              size: { xs: 6, md: 3 },
              children: (0, t.jsx)(Ct, {
                sx: { bgcolor: 'background.paper', height: '100%' },
                children: (0, t.jsxs)(vt, {
                  sx: { pb: 2 },
                  children: [
                    (0, t.jsx)(x, {
                      variant: 'caption',
                      color: 'text.secondary',
                      children: 'Total models',
                    }),
                    (0, t.jsx)(x, { variant: 'h6', children: J.totalModels }),
                  ],
                }),
              }),
            }),
            (0, t.jsx)(et, {
              size: { xs: 6, md: 3 },
              children: (0, t.jsx)(Ct, {
                sx: { bgcolor: 'background.paper', height: '100%' },
                children: (0, t.jsxs)(vt, {
                  sx: { pb: 2 },
                  children: [
                    (0, t.jsx)(x, {
                      variant: 'caption',
                      color: 'text.secondary',
                      children: 'Total PNL',
                    }),
                    (0, t.jsxs)(x, {
                      variant: 'h6',
                      sx: {
                        color: J.totalPnl >= 0 ? 'success.main' : 'error.main',
                      },
                      children: [
                        J.totalPnl >= 0 ? '+' : '',
                        J.totalPnl.toFixed(4),
                      ],
                    }),
                  ],
                }),
              }),
            }),
            (0, t.jsx)(et, {
              size: { xs: 6, md: 3 },
              children: (0, t.jsx)(Ct, {
                sx: { bgcolor: 'background.paper', height: '100%' },
                children: (0, t.jsxs)(vt, {
                  sx: { pb: 2 },
                  children: [
                    (0, t.jsx)(x, {
                      variant: 'caption',
                      color: 'text.secondary',
                      children: 'Total Positions',
                    }),
                    (0, t.jsx)(x, {
                      variant: 'h6',
                      children: J.totalPositions,
                    }),
                  ],
                }),
              }),
            }),
            (0, t.jsx)(et, {
              size: { xs: 6, md: 3 },
              children: (0, t.jsx)(Ct, {
                sx: { bgcolor: 'background.paper', height: '100%' },
                children: (0, t.jsxs)(vt, {
                  sx: { pb: 2 },
                  children: [
                    (0, t.jsx)(x, {
                      variant: 'caption',
                      color: 'text.secondary',
                      children: 'Equity (each model)',
                    }),
                    (0, t.jsx)(x, { variant: 'h6', children: '10' }),
                  ],
                }),
              }),
            }),
          ],
        }),
        (0, t.jsxs)(At, {
          direction: 'row',
          spacing: 2,
          sx: { mb: 2 },
          alignItems: 'center',
          children: [
            (0, t.jsx)(pt, {
              size: 'small',
              placeholder: 'Search...',
              value: c,
              onChange: (n) => {
                (l(n.target.value), y(0));
              },
              InputProps: {
                startAdornment: (0, t.jsx)(Re, {
                  sx: { color: 'action.active', mr: 1, fontSize: 20 },
                }),
                endAdornment:
                  c &&
                  (0, t.jsx)(ut, {
                    size: 'small',
                    onClick: () => l(''),
                    children: (0, t.jsx)(qt, { fontSize: 'small' }),
                  }),
              },
              sx: { flexGrow: 1, maxWidth: 300 },
            }),
            (0, t.jsxs)(pt, {
              select: !0,
              size: 'small',
              label: 'Status',
              value: f,
              onChange: (n) => {
                (P(n.target.value), y(0));
              },
              sx: { width: 50, flex: 1 },
              children: [
                (0, t.jsx)(_t, { value: 'All', children: 'All' }),
                (0, t.jsx)(_t, { value: 'active', children: 'Active' }),
                (0, t.jsx)(_t, { value: 'inactive', children: 'Inactive' }),
              ],
            }),
            (0, t.jsx)(D, { sx: { flexGrow: 1 } }),
            Object.keys(Y).length > 0 &&
              (0, t.jsxs)(it, {
                size: 'small',
                onClick: () => L({}),
                children: ['Show ', Object.keys(Y).length, ' Hidden Rows'],
              }),
            (0, t.jsx)(it, {
              startIcon: (0, t.jsx)(Ee, {}),
              onClick: (n) => h(n.currentTarget),
              variant: 'outlined',
              size: 'small',
              children: 'Columns',
            }),
            (0, t.jsx)($e, {
              open: !!v,
              anchorEl: v,
              onClose: () => h(null),
              anchorOrigin: { vertical: 'bottom', horizontal: 'right' },
              transformOrigin: { vertical: 'top', horizontal: 'right' },
              children: (0, t.jsxs)(D, {
                sx: { p: 2, maxHeight: 300, overflow: 'auto' },
                children: [
                  (0, t.jsx)(x, {
                    variant: 'subtitle2',
                    sx: { mb: 1 },
                    children: 'Visible Columns',
                  }),
                  (0, t.jsx)(At, {
                    children: d.map((n) =>
                      (0, t.jsx)(
                        je,
                        {
                          control: (0, t.jsx)(Ue, {
                            size: 'small',
                            checked: !!I[n],
                            onChange: () => $(n),
                          }),
                          label: n,
                        },
                        n
                      )
                    ),
                  }),
                ],
              }),
            }),
          ],
        }),
        (0, t.jsx)(Fe, {
          component: He,
          variant: 'outlined',
          children: (0, t.jsxs)(Me, {
            size: 'small',
            children: [
              (0, t.jsx)(Ne, {
                children: (0, t.jsxs)(Lt, {
                  sx: { bgcolor: 'action.hover' },
                  children: [
                    (0, t.jsx)(tt, { sx: { width: 40 }, padding: 'none' }),
                    Dt.map((n) =>
                      (0, t.jsx)(
                        tt,
                        {
                          sx: { fontWeight: 600 },
                          children: (0, t.jsx)(ze, {
                            active: s === n,
                            direction: s === n ? i : 'asc',
                            onClick: () => kt(n),
                            children: n,
                          }),
                        },
                        n
                      )
                    ),
                    (0, t.jsx)(tt, {
                      sx: { fontWeight: 600 },
                      children: 'Action',
                    }),
                  ],
                }),
              }),
              (0, t.jsxs)(Be, {
                children: [
                  mt.map((n, u) =>
                    (0, t.jsxs)(
                      Lt,
                      {
                        hover: !0,
                        children: [
                          (0, t.jsx)(tt, {
                            padding: 'none',
                            align: 'center',
                            children: (0, t.jsx)(ut, {
                              size: 'small',
                              onClick: () => at(n),
                              sx: {
                                opacity: 0.3,
                                '&:hover': { opacity: 1, color: 'error.main' },
                              },
                              children: (0, t.jsx)(qt, {
                                fontSize: 'small',
                                sx: { fontSize: 14 },
                              }),
                            }),
                          }),
                          Dt.map((T) => {
                            let k = n[T],
                              rt =
                                typeof k == 'string' &&
                                /<\/?[a-z][\s\S]*>/i.test(k);
                            return (0, t.jsx)(
                              tt,
                              {
                                children: rt
                                  ? (0, t.jsx)('div', {
                                      dangerouslySetInnerHTML: { __html: k },
                                    })
                                  : Utils?.formatUtcTime
                                    ? Utils.formatUtcTime(k)
                                    : (0, t.jsx)('div', { children: k }),
                              },
                              T
                            );
                          }),
                          (0, t.jsxs)(tt, {
                            children: [
                              (0, t.jsx)(ut, {
                                size: 'small',
                                onClick: () => St(n),
                                color: 'warning',
                                title: 'Publish to Marketplace',
                                children: (0, t.jsx)(Ae, { fontSize: 'small' }),
                              }),
                              (0, t.jsx)(ut, {
                                size: 'small',
                                onClick: () => ee(n),
                                color: 'primary',
                                title: 'Edit Config',
                                children: (0, t.jsx)(Le, { fontSize: 'small' }),
                              }),
                              (0, t.jsx)(ut, {
                                size: 'small',
                                onClick: () => ne(n),
                                color: 'primary',
                                title: 'View Equity Curve',
                                children: (0, t.jsx)(_e, { fontSize: 'small' }),
                              }),
                            ],
                          }),
                        ],
                      },
                      `${n.Identity || u}-${u}`
                    )
                  ),
                  mt.length === 0 &&
                    (0, t.jsx)(Lt, {
                      children: (0, t.jsx)(tt, {
                        colSpan: Dt.length + 2,
                        align: 'center',
                        sx: { py: 3 },
                        children: (0, t.jsx)(x, {
                          color: 'text.secondary',
                          children: 'No matching records found',
                        }),
                      }),
                    }),
                ],
              }),
            ],
          }),
        }),
        (0, t.jsx)(Oe, {
          component: 'div',
          count: j.length,
          page: m,
          rowsPerPage: S,
          rowsPerPageOptions: [10, 20, 50, 100],
          onPageChange: (n, u) => y(u),
          onRowsPerPageChange: (n) => {
            (N(Number(n.target.value)), y(0));
          },
        }),
        (0, t.jsx)(Ke, {
          open: G,
          onClose: () => !H && g(!1),
          editingRow: z,
          initialValues: V,
          onSave: oe,
          saving: H,
        }),
        (0, t.jsx)(tn, { open: w, onClose: () => R(!1), row: b, registry: o }),
        (0, t.jsx)(Jt, {
          open: A,
          onClose: () => ft(!1),
          modelIdentity: xt?.identity,
        }),
      ],
    });
  };
export { un as default };
