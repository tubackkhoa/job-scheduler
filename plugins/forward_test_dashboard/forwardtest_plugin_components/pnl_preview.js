var Mt = Object.create;
var mt = Object.defineProperty;
var Nt = Object.getOwnPropertyDescriptor;
var Ut = Object.getOwnPropertyNames;
var Ht = Object.getPrototypeOf,
    $t = Object.prototype.hasOwnProperty;
var yt = (e, o) => () => (o || e((o = {
    exports: {}
}).exports, o), o.exports);
var Ot = (e, o, i, r) => {
    if (o && typeof o == "object" || typeof o == "function")
        for (let a of Ut(o)) !$t.call(e, a) && a !== i && mt(e, a, {
            get: () => o[a],
            enumerable: !(r = Nt(o, a)) || r.enumerable
        });
    return e
};
var ht = (e, o, i) => (i = e != null ? Mt(Ht(e)) : {}, Ot(o || !e || !e.__esModule ? mt(i, "default", {
    value: e,
    enumerable: !0
}) : i, e));
var Ct = yt(et => {
    "use strict";
    var jt = Symbol.for("react.transitional.element"),
        Wt = Symbol.for("react.fragment");

    function bt(e, o, i) {
        var r = null;
        if (i !== void 0 && (r = "" + i), o.key !== void 0 && (r = "" + o.key), "key" in o) {
            i = {};
            for (var a in o) a !== "key" && (i[a] = o[a])
        } else i = o;
        return o = i.ref, {
            $$typeof: jt,
            type: e,
            key: r,
            ref: o !== void 0 ? o : null,
            props: i
        }
    }
    et.Fragment = Wt;
    et.jsx = bt;
    et.jsxs = bt
});
var lt = yt((Te, Tt) => {
    "use strict";
    Tt.exports = Ct()
});
var t = ht(lt(), 1),
    {
        useCallback: Gt,
        useEffect: j,
        useMemo: X,
        useRef: vt,
        useState: u
    } = React,
    {
        createChart: qt,
        IChartApi: ve,
        LineData: xe,
        LineSeries: xt,
        MouseEventParams: Pe,
        UTCTimestamp: Se
    } = LightweightChart,
    {
        ViewColumn: Vt,
        FilterList: Yt,
        Clear: Pt,
        Settings: Jt,
        ShowChart: Xt
    } = MuiIcon,
    {
        Table: Zt,
        TableBody: Qt,
        TableCell: M,
        TableContainer: Kt,
        TableHead: te,
        TableRow: ct,
        TableSortLabel: ee,
        TablePagination: ne,
        TextField: Q,
        Box: b,
        Checkbox: oe,
        FormControlLabel: ie,
        Stack: ut,
        IconButton: nt,
        Button: W,
        Card: ot,
        CardContent: it,
        Typography: f,
        Grid: N,
        Popover: re,
        Paper: ae,
        MenuItem: dt,
        Dialog: Dt,
        DialogTitle: It,
        DialogContent: kt,
        DialogActions: Lt,
        CircularProgress: se
    } = Mui,
    D = {
        positive: "#28a745",
        negative: "#dc3545",
        neutral: "#6c757d",
        warning: "#ffc107"
    };

function z(e, o, i = !1) {
    return `<span style="color:${o};${i?"font-weight:bold;":""}">${e}</span>`
}

function Z(e) {
    return e == null ? "-" : e > 0 ? z(`\u2197 +${e.toFixed(4)}%`, D.positive, !0) : e < 0 ? z(`\u2198 $${e.toFixed(4)}`, D.negative, !0) : z("$0.0000", D.neutral)
}

function le(e) {
    return e ? e.state === "active" ? z(`\u2713 Active (${e.label})`, D.positive) : e.state === "inactive" ? z(`\u23F8 Inactive (${e.label})`, D.warning) : z("\u2298 No Job", D.neutral) : "-"
}

function ce(e) {
    if (!e) return "-";
    let o = e.direction === "BUY" || e.direction === "LONG" ? D.positive : D.negative;
    return `${z(e.symbol,o,!0)} ${Z(e.pnl)}`
}

function de(e) {
    if (e == null) return "-";
    let o = e * 100,
        i = D.negative;
    return o >= 50 ? i = D.positive : o >= 40 && (i = D.neutral), z(`${o.toFixed(1)}%`, i, !0)
}

function ue(e) {
    if (!e) return "-";
    let o = new Date(e);
    if (isNaN(o.getTime())) return "-";
    let i = o.getUTCFullYear(),
        r = String(o.getUTCMonth() + 1).padStart(2, "0"),
        a = String(o.getUTCDate()).padStart(2, "0"),
        C = String(o.getUTCHours()).padStart(2, "0"),
        c = String(o.getUTCMinutes()).padStart(2, "0");
    return `${i}-${r}-${a} ${C}:${c} UTC`
}

function ge(e, o) {
    if (!e?.length) return {
        rows: [],
        totals: {
            total_models: 0,
            total_pnl: 0,
            total_positions: 0
        }
    };
    let i = {};
    for (let l of e) {
        let d = l.identity;
        d && (i[d] = l)
    }
    e = Object.values(i);
    let r = {};
    for (let l of o) {
        let d = l?.config?.model_key;
        d && (r[d] = {
            state: l.active ? "active" : "inactive",
            label: l.description || "No description"
        })
    }
    let a = [],
        C = 0,
        c = 0;
    for (let l of e) {
        let d = l.identity;
        if (!d) continue;
        let P = l.totalPnl ?? 0,
            p = Number(l.totalPositions ?? 0);
        C += P, c += p;
        let y = l.lastPosition,
            v = y ? {
                symbol: y.symbol ?? "",
                direction: y.side ?? "",
                pnl: y.pnl ?? 0
            } : null,
            E = y?.time ?? null,
            T = r[d];
        a.push({
            Identity: d,
            Model: l.modelName,
            "Total PNL": Z(P),
            "PNL 1H": Z(l.pnlDelta1h ?? 0),
            "PNL 4H": Z(l.pnlDelta4h ?? 0),
            "PNL 1D": Z(l.pnlDelta1d ?? 0),
            Winrate: de(l.winrate),
            "Max Drawdown": l.maxDrawdown,
            "Latest Position": ce(v),
            "Latest Position Time": E,
            Status: le(T),
            "Hide Status": T?.state ?? "",
            Started: ue(l.startedAt ?? ""),
            "Total Positions": p,
            "Total Runtime": l.totalRunningTime ?? "-"
        })
    }
    return {
        rows: a,
        totals: {
            total_models: a.length,
            total_pnl: C,
            total_positions: c
        }
    }
}

function St(e) {
    return e ? new Date(e).toISOString().replace("T", " ").slice(0, 19) + " UTC" : ""
}
var pe = React.memo(({
    visible: e,
    x: o,
    y: i,
    data: r
}) => !e || !r ? null : (0, t.jsxs)(b, {
    sx: {
        position: "absolute",
        left: o,
        top: i,
        bgcolor: "rgba(0,0,0,0.85)",
        color: "#fff",
        px: 1.5,
        py: 1,
        borderRadius: 1,
        fontSize: 12,
        pointerEvents: "none",
        zIndex: 10,
        minWidth: 220,
        boxShadow: 3
    },
    children: [(0, t.jsxs)(f, {
        variant: "caption",
        display: "block",
        children: [(0, t.jsx)("strong", {
            children: "Open time:"
        }), " ", r.openTime]
    }), (0, t.jsxs)(f, {
        variant: "caption",
        display: "block",
        children: [(0, t.jsx)("strong", {
            children: "Close time:"
        }), " ", r.time]
    }), (0, t.jsxs)(f, {
        variant: "caption",
        display: "block",
        children: [(0, t.jsx)("strong", {
            children: "Symbol:"
        }), " ", r.symbol, " | ", (0, t.jsx)("strong", {
            children: "Side:"
        }), " ", (0, t.jsx)(b, {
            component: "span",
            sx: {
                color: r.side === "BUY" ? "#4caf50" : "#f44336",
                fontWeight: 600
            },
            children: r.side
        })]
    }), (0, t.jsx)(b, {
        sx: {
            my: .5,
            borderTop: "1px solid rgba(255,255,255,0.2)"
        }
    }), (0, t.jsxs)(f, {
        variant: "caption",
        display: "block",
        children: [(0, t.jsx)("strong", {
            children: "PnL:"
        }), " ", (0, t.jsxs)(b, {
            component: "span",
            sx: {
                color: r.pnl >= 0 ? "#4caf50" : "#f44336",
                fontWeight: 600
            },
            children: [r.pnl >= 0 ? "+" : "", r.pnl.toFixed(4)]
        })]
    }), (0, t.jsxs)(f, {
        variant: "caption",
        display: "block",
        children: [(0, t.jsx)("strong", {
            children: "Accumulated:"
        }), " ", (0, t.jsxs)(b, {
            component: "span",
            sx: {
                color: r.accumulatedPnl >= 0 ? "#2962FF" : "#f44336",
                fontWeight: 600
            },
            children: [r.accumulatedPnl >= 0 ? "+" : "", r.accumulatedPnl.toFixed(4)]
        })]
    })]
}));

function rt(e) {
    if (typeof e == "number") return e;
    if (typeof e == "string") {
        let i = e.replace(/<[^>]*>/g, "").replace(/[^\d.-]/g, ""),
            r = parseFloat(i);
        return isNaN(r) ? 0 : r
    }
    return 0
}

function wt(e, o, i) {
    let r = e[i],
        a = o[i];
    if (typeof r == "string" && typeof a == "string" && /^\d{4}-\d{2}-\d{2}T/.test(r) && /^\d{4}-\d{2}-\d{2}T/.test(a)) {
        let P = Date.parse(r),
            p = Date.parse(a);
        if (!isNaN(P) && !isNaN(p)) return p < P ? -1 : p > P ? 1 : 0
    }
    let C = rt(r),
        c = rt(a);
    if (C !== c) return C < c ? 1 : -1;
    let l = String(r ?? "").toLowerCase(),
        d = String(a ?? "").toLowerCase();
    return d < l ? -1 : d > l ? 1 : 0
}

function fe(e, o) {
    return e === "desc" ? (i, r) => wt(i, r, o) : (i, r) => -wt(i, r, o)
}
var me = ["tp_pct", "sl_pct", "top_k", "start_date"],
  ye = ({ open: e, onClose: o, editingRow: i, initialValues: r, onSave: a, saving: C }) => {
    if (!i) return null;

    let [c, l] = u(r || {});
    j(() => { l(r || {}) }, [r, e]);

    let d = (p, y) => l(v => ({ ...v, [p]: y })),
      P = () => a(c);

    return (0, t.jsxs)(Dt, {
      open: e,
      onClose: o,
      maxWidth: "sm",
      fullWidth: !0,
      children: [
        (0, t.jsxs)(It, { children: ["Edit Config: ", i.Identity || "Unknown"] }),
        (0, t.jsx)(kt, {
          dividers: !0,
          children: (0, t.jsx)(N, {
            container: !0,
            spacing: 2,
            sx: { pt: 1 },
            children: me.map(p => {
              // ✅ start_date as native date picker
              if (p === "start_date") {
                let y = c[p] ?? ""; // expected "YYYY-MM-DD"
                return (0, t.jsx)(N, {
                  size: { sm: 6 },
                  children: (0, t.jsx)(Q, {
                    fullWidth: !0,
                    size: "small",
                    label: p,
                    type: "date",
                    value: y,
                    // để label không đè lên value khi type=date
                    InputLabelProps: { shrink: !0 },
                    onChange: E => d(p, E.target.value) // "YYYY-MM-DD"
                  })
                }, p);
              }

              // numeric fields
              let y = c[p],
                v = typeof y == "number" || p === "tp_pct" || p === "sl_pct" || p === "top_k";

              return (0, t.jsx)(N, {
                size: { sm: 6 },
                children: (0, t.jsx)(Q, {
                  fullWidth: !0,
                  size: "small",
                  label: p,
                  value: y ?? "",
                  type: v ? "number" : "text",
                  onChange: E => {
                    let T = v ? parseFloat(E.target.value) : E.target.value;
                    d(p, T);
                  }
                })
              }, p);
            })
          })
        }),
        (0, t.jsxs)(Lt, {
          children: [
            (0, t.jsx)(W, { onClick: o, disabled: C, color: "inherit", children: "Cancel" }),
            (0, t.jsx)(W, { onClick: P, disabled: C, variant: "contained", children: C ? "Saving..." : "Save Changes" })
          ]
        })
      ]
    });
  },
    he = ({
        open: e,
        onClose: o,
        row: i,
        registry: r
    }) => {
        let [a, C] = u(!1), [c, l] = u([]), [d, P] = u(null), [p, y] = u(""), [v, E] = u(""), T = vt(null), k = vt(null), [U, R] = u({
            visible: !1,
            x: 0,
            y: 0
        }), G = Gt(async () => {
            if (i) {
                C(!0), P(null);
                try {
                    let g = Utils.buildJinjaContext(r.formContext.pluginPackage, r.formContext.formData),
                        H = i.Identity || i.id,
                        B = _ => _ ? `${_}:00Z` : "",
                        q = B(p),
                        V = B(v),
                        F = await g("{{ get_equity_curve_forward_test(webhook_url, webhook_api_key, identity, startTime, endTime) }}", {
                            identity: H,
                            startTime: q,
                            endTime: V
                        });
                    F && Array.isArray(F) ? l(F) : l([])
                } catch (g) {
                    console.error("Failed to fetch equity curve", g), P("Failed to load chart data: " + g.message), l([])
                } finally {
                    C(!1)
                }
            }
        }, [i, p, v, Utils, r]);
        return j(() => {
            e || R(g => ({
                ...g,
                visible: !1
            }))
        }, [e]), j(() => {
            e && i && G()
        }, [e, i, G]), j(() => {
            if (!e || !T.current || c.length === 0) return;
            k.current?.remove(), k.current = null;
            let g = qt(T.current, {
                width: T.current.clientWidth,
                height: 500,
                layout: {
                    background: {
                        color: "#ffffff"
                    },
                    textColor: "#333"
                },
                grid: {
                    vertLines: {
                        color: "#e1e8ed"
                    },
                    horzLines: {
                        color: "#e1e8ed"
                    }
                },
                crosshair: {
                    mode: 1,
                    vertLine: {
                        width: 1,
                        color: "#758696",
                        style: 3
                    },
                    horzLine: {
                        width: 1,
                        color: "#758696",
                        style: 3
                    }
                },
                timeScale: {
                    timeVisible: !0,
                    secondsVisible: !1,
                    borderColor: "#d1d4dc"
                },
                rightPriceScale: {
                    borderColor: "#d1d4dc"
                }
            });
            k.current = g;
            let H = g.addSeries(xt, {
                    color: "#FF6B00",
                    lineWidth: 2,
                    title: "PnL"
                }),
                B = g.addSeries(xt, {
                    color: "#2962FF",
                    lineWidth: 2,
                    title: "Accumulated PnL"
                }),
                q = c.map(x => ({
                    time: new Date(x.time).getTime() / 1e3,
                    value: x.pnl
                })),
                V = c.map(x => ({
                    time: new Date(x.time).getTime() / 1e3,
                    value: x.accumulatedPnl
                }));
            H.setData(q), B.setData(V), g.timeScale().fitContent();
            let F = Utils._.throttle(x => {
                if (!x?.time || !x?.point) {
                    R(S => ({
                        ...S,
                        visible: !1
                    }));
                    return
                }
                if (x.point.x < 0 || x.point.y < 0) {
                    R(S => ({
                        ...S,
                        visible: !1
                    }));
                    return
                }
                let K = x.seriesData.get(B);
                if (!K) {
                    R(S => ({
                        ...S,
                        visible: !1
                    }));
                    return
                }
                let $ = K.time * 1e3,
                    I = c.find(S => Math.abs(new Date(S.time).getTime() - $) < 1e3);
                if (!I) return;
                let L = T.current.clientWidth - 240,
                    tt = T.current.clientHeight - 120;
                R({
                    visible: !0,
                    x: Math.min(x.point.x + 15, L),
                    y: Math.min(x.point.y + 15, tt),
                    data: {
                        time: St(I.time),
                        openTime: St(I.openTime),
                        symbol: I.symbol,
                        side: I.side,
                        pnl: I.pnl,
                        accumulatedPnl: I.accumulatedPnl
                    }
                })
            }, 40);
            g.subscribeCrosshairMove(F);
            let _ = () => {
                !k.current || !T.current || k.current.applyOptions({
                    width: T.current.clientWidth
                })
            };
            return window.addEventListener("resize", _), () => {
                window.removeEventListener("resize", _), g.unsubscribeCrosshairMove(F), g.remove(), k.current = null
            }
        }, [c, e]), (0, t.jsxs)(Dt, {
            open: e,
            onClose: o,
            maxWidth: "xl",
            fullWidth: !0,
            children: [(0, t.jsxs)(It, {
                children: ["Equity Curve: ", i?.Identity || "Unknown"]
            }), (0, t.jsxs)(kt, {
                children: [(0, t.jsxs)(ut, {
                    direction: "row",
                    spacing: 2,
                    sx: {
                        mb: 2,
                        mt: 1
                    },
                    children: [(0, t.jsx)(Q, {
                        label: "Start Time",
                        type: "datetime-local",
                        value: p,
                        onChange: g => y(g.target.value),
                        size: "small",
                        InputLabelProps: {
                            shrink: !0
                        },
                        sx: {
                            flex: 1
                        }
                    }), (0, t.jsx)(Q, {
                        label: "End Time",
                        type: "datetime-local",
                        value: v,
                        onChange: g => E(g.target.value),
                        size: "small",
                        InputLabelProps: {
                            shrink: !0
                        },
                        sx: {
                            flex: 1
                        }
                    }), (0, t.jsx)(W, {
                        variant: "contained",
                        onClick: G,
                        disabled: a,
                        sx: {
                            height: 40,
                            alignSelf: "flex-start"
                        },
                        children: "Refresh"
                    })]
                }), (0, t.jsxs)(b, {
                    sx: {
                        display: "flex",
                        gap: 3,
                        mb: 2,
                        justifyContent: "center"
                    },
                    children: [(0, t.jsxs)(b, {
                        sx: {
                            display: "flex",
                            alignItems: "center",
                            gap: 1
                        },
                        children: [(0, t.jsx)(b, {
                            sx: {
                                width: 20,
                                height: 3,
                                bgcolor: "#FF6B00",
                                borderRadius: 1
                            }
                        }), (0, t.jsx)(f, {
                            variant: "body2",
                            children: "PnL (Individual Trade)"
                        })]
                    }), (0, t.jsxs)(b, {
                        sx: {
                            display: "flex",
                            alignItems: "center",
                            gap: 1
                        },
                        children: [(0, t.jsx)(b, {
                            sx: {
                                width: 20,
                                height: 3,
                                bgcolor: "#2962FF",
                                borderRadius: 1
                            }
                        }), (0, t.jsx)(f, {
                            variant: "body2",
                            children: "Accumulated PnL"
                        })]
                    })]
                }), a && (0, t.jsx)(b, {
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    minHeight: 400,
                    children: (0, t.jsx)(se, {})
                }), d && (0, t.jsx)(b, {
                    minHeight: 400,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    children: (0, t.jsx)(f, {
                        color: "error",
                        children: d
                    })
                }), !a && !d && c.length === 0 && (0, t.jsx)(b, {
                    minHeight: 400,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    children: (0, t.jsx)(f, {
                        color: "text.secondary",
                        children: "No data available"
                    })
                }), !a && !d && c.length > 0 && (0, t.jsx)(b, {
                    ref: T,
                    sx: {
                        position: "relative",
                        width: "100%",
                        height: 540,
                        mt: 2
                    },
                    children: (0, t.jsx)(pe, {
                        ...U
                    })
                })]
            }), (0, t.jsx)(Lt, {
                children: (0, t.jsx)(W, {
                    variant: "contained",
                    color: "warning",
                    onClick: o,
                    children: "Close"
                })
            })]
        })
    },
    we = ({
        formData: e,
        registry: o
    }) => {
        let [i, r] = u("desc"), [a, C] = u(""), [c, l] = u(""), [d, P] = u("All"), [p, y] = u(0), [v, E] = u(10), [T, k] = u(null), [U, R] = u(null), [G, g] = u(!1), [H, B] = u(!1), [q, V] = u({}), [F, _] = u(!1), [x, K] = u(null), [$, I] = u({}), [L, tt] = u([]);
        j(() => {
            if (e) try {
                let {
                    models: n,
                    jobList: s,
                    stats: m
                } = Utils.convertByType(e, "object"), {
                    rows: h
                } = ge(m, s), J = Object.fromEntries(n.map(A => [A.identity, A.currentConfig])), w = h.map(A => ({
                    ...A,
                    "Hide currentConfig": J[A.Identity]
                }));
                console.log(w), tt(w)
            } catch (n) {
                console.error(n)
            }
        }, [e]);
        let S = X(() => L.length === 0 ? [] : Object.keys(L[0]).filter(n => !n.includes("Hide") && n !== "config"), [L]),
            [gt, pt] = u({});
        j(() => {
            S.length > 0 && pt(n => {
                let s = {
                        ...n
                    },
                    m = !1;
                return S.forEach(h => {
                    s[h] === void 0 && (s[h] = !0, m = !0)
                }), m ? s : n
            })
        }, [S]);
        let O = X(() => {
                if (!L) return [];
                let n = L;
                if (n = n.filter(s => !$[s.Identity || s.id]), c) {
                    let s = c.toLowerCase();
                    n = n.filter(m => Object.values(m).some(h => String(h).toLowerCase().includes(s)))
                }
                return d !== "All" && (n = n.filter(s => {
                    let m = String(s["Hide Status"]).toLowerCase();
                    return m ? m === d : !1
                })), n
            }, [L, c, $, d]),
            at = X(() => a ? [...O].sort(fe(i, a)) : O, [O, i, a]),
            ft = X(() => {
                let n = p * v;
                return at.slice(n, n + v)
            }, [at, p, v]),
            Y = X(() => {
                let n = O.length,
                    s = 0,
                    m = 0;
                return O.forEach(h => {
                    s += rt(h["Total PNL"]), m += rt(h["Total Positions"])
                }), {
                    totalModels: n,
                    totalPnl: s,
                    totalPositions: m
                }
            }, [O]),
            Et = n => {
                r(a === n && i === "asc" ? "desc" : "asc"), C(n)
            },
            Rt = n => {
                pt(s => ({
                    ...s,
                    [n]: !s[n]
                }))
            },
            Bt = n => {
                let s = n.Identity || JSON.stringify(n);
                I(m => ({
                    ...m,
                    [s]: !0
                }))
            },
            Ft = n => {
                R(n);
                let s = n["Hide currentConfig"] || n.config || {};
                V(s.config), g(!0)
            },
            _t = n => {
                K(n), _(!0)
            },
            zt = async n => {
                if (!(!U || !o)) {
                    B(!0);
                    try {
                        let s = Utils.buildJinjaContext(o.formContext.pluginPackage, o.formContext.formData),
                            m = {
                                ...n
                            },
                            h = U.Identity;
                        await s("{{ update_model_config(identity, payload) }}", {
                            identity: h,
                            payload: m
                        }), tt(J => J.map(w => {
                            let A = w.Identity,
                                At = U.Identity;
                            if (A === At) {
                                if (w["Hide currentConfig"]) return {
                                    ...w,
                                    "Hide currentConfig": {
                                        ...w["Hide currentConfig"],
                                        config: {
                                            ...w["Hide currentConfig"].config,
                                            ...n
                                        }
                                    }
                                };
                                if (w.config) return {
                                    ...w,
                                    config: {
                                        ...w.config,
                                        ...n
                                    }
                                }
                            }
                            return w
                        })), g(!1), R(null), alert("Update config completed")
                    } catch (s) {
                        console.error("Failed to update config", s), alert("Failed to update config: " + s.message)
                    } finally {
                        B(!1)
                    }
                }
            }, st = S.filter(n => gt[n]);
        return L.length ? (0, t.jsxs)(b, {
            children: [(0, t.jsxs)(N, {
                container: !0,
                spacing: 2,
                sx: {
                    mb: 2
                },
                children: [(0, t.jsx)(N, {
                    size: {
                        xs: 6,
                        md: 3
                    },
                    children: (0, t.jsx)(ot, {
                        sx: {
                            bgcolor: "background.paper",
                            height: "100%"
                        },
                        children: (0, t.jsxs)(it, {
                            sx: {
                                pb: 2
                            },
                            children: [(0, t.jsx)(f, {
                                variant: "caption",
                                color: "text.secondary",
                                children: "Total models"
                            }), (0, t.jsx)(f, {
                                variant: "h6",
                                children: Y.totalModels
                            })]
                        })
                    })
                }), (0, t.jsx)(N, {
                    size: {
                        xs: 6,
                        md: 3
                    },
                    children: (0, t.jsx)(ot, {
                        sx: {
                            bgcolor: "background.paper",
                            height: "100%"
                        },
                        children: (0, t.jsxs)(it, {
                            sx: {
                                pb: 2
                            },
                            children: [(0, t.jsx)(f, {
                                variant: "caption",
                                color: "text.secondary",
                                children: "Total PNL"
                            }), (0, t.jsxs)(f, {
                                variant: "h6",
                                sx: {
                                    color: Y.totalPnl >= 0 ? "success.main" : "error.main"
                                },
                                children: [Y.totalPnl >= 0 ? "+" : "", Y.totalPnl.toFixed(4)]
                            })]
                        })
                    })
                }), (0, t.jsx)(N, {
                    size: {
                        xs: 6,
                        md: 3
                    },
                    children: (0, t.jsx)(ot, {
                        sx: {
                            bgcolor: "background.paper",
                            height: "100%"
                        },
                        children: (0, t.jsxs)(it, {
                            sx: {
                                pb: 2
                            },
                            children: [(0, t.jsx)(f, {
                                variant: "caption",
                                color: "text.secondary",
                                children: "Total Positions"
                            }), (0, t.jsx)(f, {
                                variant: "h6",
                                children: Y.totalPositions
                            })]
                        })
                    })
                }), (0, t.jsx)(N, {
                    size: {
                        xs: 6,
                        md: 3
                    },
                    children: (0, t.jsx)(ot, {
                        sx: {
                            bgcolor: "background.paper",
                            height: "100%"
                        },
                        children: (0, t.jsxs)(it, {
                            sx: {
                                pb: 2
                            },
                            children: [(0, t.jsx)(f, {
                                variant: "caption",
                                color: "text.secondary",
                                children: "Equity (each model)"
                            }), (0, t.jsx)(f, {
                                variant: "h6",
                                children: "10"
                            })]
                        })
                    })
                })]
            }), (0, t.jsxs)(ut, {
                direction: "row",
                spacing: 2,
                sx: {
                    mb: 2
                },
                alignItems: "center",
                children: [(0, t.jsx)(Q, {
                    size: "small",
                    placeholder: "Search...",
                    value: c,
                    onChange: n => {
                        l(n.target.value), y(0)
                    },
                    InputProps: {
                        startAdornment: (0, t.jsx)(Yt, {
                            sx: {
                                color: "action.active",
                                mr: 1,
                                fontSize: 20
                            }
                        }),
                        endAdornment: c && (0, t.jsx)(nt, {
                            size: "small",
                            onClick: () => l(""),
                            children: (0, t.jsx)(Pt, {
                                fontSize: "small"
                            })
                        })
                    },
                    sx: {
                        flexGrow: 1,
                        maxWidth: 300
                    }
                }), (0, t.jsxs)(Q, {
                    select: !0,
                    size: "small",
                    label: "Status",
                    value: d,
                    onChange: n => {
                        P(n.target.value), y(0)
                    },
                    sx: {
                        width: 50,
                        flex: 1
                    },
                    children: [(0, t.jsx)(dt, {
                        value: "All",
                        children: "All"
                    }), (0, t.jsx)(dt, {
                        value: "active",
                        children: "Active"
                    }), (0, t.jsx)(dt, {
                        value: "inactive",
                        children: "Inactive"
                    })]
                }), (0, t.jsx)(b, {
                    sx: {
                        flexGrow: 1
                    }
                }), Object.keys($).length > 0 && (0, t.jsxs)(W, {
                    size: "small",
                    onClick: () => I({}),
                    children: ["Show ", Object.keys($).length, " Hidden Rows"]
                }), (0, t.jsx)(W, {
                    startIcon: (0, t.jsx)(Vt, {}),
                    onClick: n => k(n.currentTarget),
                    variant: "outlined",
                    size: "small",
                    children: "Columns"
                }), (0, t.jsx)(re, {
                    open: !!T,
                    anchorEl: T,
                    onClose: () => k(null),
                    anchorOrigin: {
                        vertical: "bottom",
                        horizontal: "right"
                    },
                    transformOrigin: {
                        vertical: "top",
                        horizontal: "right"
                    },
                    children: (0, t.jsxs)(b, {
                        sx: {
                            p: 2,
                            maxHeight: 300,
                            overflow: "auto"
                        },
                        children: [(0, t.jsx)(f, {
                            variant: "subtitle2",
                            sx: {
                                mb: 1
                            },
                            children: "Visible Columns"
                        }), (0, t.jsx)(ut, {
                            children: S.map(n => (0, t.jsx)(ie, {
                                control: (0, t.jsx)(oe, {
                                    size: "small",
                                    checked: !!gt[n],
                                    onChange: () => Rt(n)
                                }),
                                label: n
                            }, n))
                        })]
                    })
                })]
            }), (0, t.jsx)(Kt, {
                component: ae,
                variant: "outlined",
                children: (0, t.jsxs)(Zt, {
                    size: "small",
                    children: [(0, t.jsx)(te, {
                        children: (0, t.jsxs)(ct, {
                            sx: {
                                bgcolor: "action.hover"
                            },
                            children: [(0, t.jsx)(M, {
                                sx: {
                                    width: 40
                                },
                                padding: "none"
                            }), st.map(n => (0, t.jsx)(M, {
                                sx: {
                                    fontWeight: 600
                                },
                                children: (0, t.jsx)(ee, {
                                    active: a === n,
                                    direction: a === n ? i : "asc",
                                    onClick: () => Et(n),
                                    children: n
                                })
                            }, n)), (0, t.jsx)(M, {
                                sx: {
                                    fontWeight: 600
                                },
                                children: "Action"
                            })]
                        })
                    }), (0, t.jsxs)(Qt, {
                        children: [ft.map((n, s) => (0, t.jsxs)(ct, {
                            hover: !0,
                            children: [(0, t.jsx)(M, {
                                padding: "none",
                                align: "center",
                                children: (0, t.jsx)(nt, {
                                    size: "small",
                                    onClick: () => Bt(n),
                                    sx: {
                                        opacity: .3,
                                        "&:hover": {
                                            opacity: 1,
                                            color: "error.main"
                                        }
                                    },
                                    children: (0, t.jsx)(Pt, {
                                        fontSize: "small",
                                        sx: {
                                            fontSize: 14
                                        }
                                    })
                                })
                            }), st.map(m => {
                                let h = n[m],
                                    J = typeof h == "string" && /<\/?[a-z][\s\S]*>/i.test(h);
                                return (0, t.jsx)(M, {
                                    children: J ? (0, t.jsx)("div", {
                                        dangerouslySetInnerHTML: {
                                            __html: h
                                        }
                                    }) : Utils?.formatUtcTime ? Utils.formatUtcTime(h) : (0, t.jsx)("div", {
                                        children: h
                                    })
                                }, m)
                            }), (0, t.jsxs)(M, {
                                children: [(0, t.jsx)(nt, {
                                    size: "small",
                                    onClick: () => Ft(n),
                                    color: "primary",
                                    title: "Edit Config",
                                    children: (0, t.jsx)(Jt, {
                                        fontSize: "small"
                                    })
                                }), (0, t.jsx)(nt, {
                                    size: "small",
                                    onClick: () => _t(n),
                                    color: "primary",
                                    title: "View Equity Curve",
                                    children: (0, t.jsx)(Xt, {
                                        fontSize: "small"
                                    })
                                })]
                            })]
                        }, `${n.Identity||s}-${s}`)), ft.length === 0 && (0, t.jsx)(ct, {
                            children: (0, t.jsx)(M, {
                                colSpan: st.length + 1,
                                align: "center",
                                sx: {
                                    py: 3
                                },
                                children: (0, t.jsx)(f, {
                                    color: "text.secondary",
                                    children: "No matching records found"
                                })
                            })
                        })]
                    })]
                })
            }), (0, t.jsx)(ne, {
                component: "div",
                count: at.length,
                page: p,
                rowsPerPage: v,
                rowsPerPageOptions: [10, 20, 50, 100],
                onPageChange: (n, s) => y(s),
                onRowsPerPageChange: n => {
                    E(Number(n.target.value)), y(0)
                }
            }), (0, t.jsx)(ye, {
                open: G,
                onClose: () => !H && g(!1),
                editingRow: U,
                initialValues: q,
                onSave: zt,
                saving: H
            }), (0, t.jsx)(he, {
                open: F,
                onClose: () => _(!1),
                row: x,
                registry: o
            })]
        }) : (0, t.jsx)(f, {
            color: "text.secondary",
            children: "No data available"
        })
    };
export {
    we as
    default
};