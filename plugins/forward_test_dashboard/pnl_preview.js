var ye = Object.create;
var $ = Object.defineProperty;
var be = Object.getOwnPropertyDescriptor;
var Te = Object.getOwnPropertyNames;
var fe = Object.getPrototypeOf,
  xe = Object.prototype.hasOwnProperty;
var U = (r, n) => () => (n || r((n = { exports: {} }).exports, n), n.exports);
var Ce = (r, n, o, a) => {
  if ((n && typeof n == 'object') || typeof n == 'function')
    for (let i of Te(n))
      !xe.call(r, i) &&
        i !== o &&
        $(r, i, {
          get: () => n[i],
          enumerable: !(a = be(n, i)) || a.enumerable,
        });
  return r;
};
var Q = (r, n, o) => (
  (o = r != null ? ye(fe(r)) : {}),
  Ce(
    n || !r || !r.__esModule
      ? $(o, 'default', { value: r, enumerable: !0 })
      : o,
    r
  )
);
var Z = U((N) => {
  'use strict';
  var ve = Symbol.for('react.transitional.element'),
    Pe = Symbol.for('react.fragment');
  function X(r, n, o) {
    var a = null;
    if (
      (o !== void 0 && (a = '' + o),
      n.key !== void 0 && (a = '' + n.key),
      'key' in n)
    ) {
      o = {};
      for (var i in n) i !== 'key' && (o[i] = n[i]);
    } else o = n;
    return (
      (n = o.ref),
      { $$typeof: ve, type: r, key: a, ref: n !== void 0 ? n : null, props: o }
    );
  }
  N.Fragment = Pe;
  N.jsx = X;
  N.jsxs = X;
});
var F = U((Ne, K) => {
  'use strict';
  K.exports = Z();
});
var e = Q(F(), 1);
function B(r) {
  if (typeof r == 'number') return r;
  if (typeof r == 'string') {
    let o = r.replace(/<[^>]*>/g, '').replace(/[^\d.-]/g, ''),
      a = parseFloat(o);
    return isNaN(a) ? 0 : a;
  }
  return 0;
}
function ee(r, n, o) {
  let a = r[o],
    i = n[o];
  if (
    typeof a == 'string' &&
    typeof i == 'string' &&
    /^\d{4}-\d{2}-\d{2}T/.test(a) &&
    /^\d{4}-\d{2}-\d{2}T/.test(i)
  ) {
    let y = Date.parse(a),
      p = Date.parse(i);
    if (!isNaN(y) && !isNaN(p)) return p < y ? -1 : p > y ? 1 : 0;
  }
  let C = B(a),
    v = B(i);
  if (C !== v) return C < v ? 1 : -1;
  let u = String(a ?? '').toLowerCase(),
    P = String(i ?? '').toLowerCase();
  return P < u ? -1 : P > u ? 1 : 0;
}
function Se(r, n) {
  return r === 'desc' ? (o, a) => ee(o, a, n) : (o, a) => -ee(o, a, n);
}
var Be = ({ formData: r, Mui: n, React: o, MuiIcon: a, Utils: i }) => {
  let {
      Table: C,
      TableBody: v,
      TableCell: u,
      TableContainer: P,
      TableHead: y,
      TableRow: p,
      TableSortLabel: te,
      TablePagination: oe,
      TextField: ne,
      Box: I,
      Checkbox: re,
      FormControlLabel: se,
      Stack: j,
      IconButton: G,
      Button: H,
      Card: S,
      CardContent: k,
      Typography: c,
      Grid: b,
      Popover: ae,
      Paper: ie,
      Divider: ke,
      MenuItem: we,
    } = n,
    { ViewColumn: le, FilterList: ce, Clear: _ } = a,
    [w, de] = o.useState('desc'),
    [m, ue] = o.useState(''),
    [T, V] = o.useState(''),
    [L, M] = o.useState(0),
    [z, pe] = o.useState(20),
    [q, D] = o.useState(null),
    [E, R] = o.useState({}),
    g = o.useMemo(() => {
      if (!r) return [];
      try {
        let t = JSON.parse(r);
        return Array.isArray(t) ? t : [];
      } catch {
        return [];
      }
    }, [r]),
    f = o.useMemo(() => (g.length === 0 ? [] : Object.keys(g[0])), [g]),
    [J, W] = o.useState({});
  o.useEffect(() => {
    f.length > 0 &&
      W((t) => {
        let s = { ...t },
          l = !1;
        return (
          f.forEach((d) => {
            s[d] === void 0 && ((s[d] = !0), (l = !0));
          }),
          l ? s : t
        );
      });
  }, [f]);
  let h = o.useMemo(() => {
      if (!g) return [];
      let t = g;
      if (((t = t.filter((s) => !E[s.Identity || s.id])), T)) {
        let s = T.toLowerCase();
        t = t.filter((l) =>
          Object.values(l).some((d) => String(d).toLowerCase().includes(s))
        );
      }
      return t;
    }, [g, T, E]),
    O = o.useMemo(() => (m ? [...h].sort(Se(w, m)) : h), [h, w, m]),
    Y = o.useMemo(() => {
      let t = L * z;
      return O.slice(t, t + z);
    }, [O, L, z]),
    x = o.useMemo(() => {
      let t = h.length,
        s = 0,
        l = 0;
      return (
        h.forEach((d) => {
          ((s += B(d['Total PNL'])), (l += B(d['Total Positions'])));
        }),
        { totalModels: t, totalPnl: s, totalPositions: l }
      );
    }, [h]),
    ge = (t) => {
      (de(m === t && w === 'asc' ? 'desc' : 'asc'), ue(t));
    },
    me = (t) => {
      W((s) => ({ ...s, [t]: !s[t] }));
    },
    he = (t) => {
      let s = t.Identity || JSON.stringify(t);
      R((l) => ({ ...l, [s]: !0 }));
    },
    A = f.filter((t) => J[t]);
  return g.length
    ? (0, e.jsxs)(I, {
        children: [
          (0, e.jsxs)(b, {
            container: !0,
            spacing: 2,
            sx: { mb: 2 },
            children: [
              (0, e.jsx)(b, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(S, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(k, {
                    sx: { pb: 2 },
                    children: [
                      (0, e.jsx)(c, {
                        variant: 'caption',
                        color: 'text.secondary',
                        children: 'Total models',
                      }),
                      (0, e.jsx)(c, { variant: 'h6', children: x.totalModels }),
                    ],
                  }),
                }),
              }),
              (0, e.jsx)(b, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(S, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(k, {
                    sx: { pb: 2 },
                    children: [
                      (0, e.jsx)(c, {
                        variant: 'caption',
                        color: 'text.secondary',
                        children: 'Total PNL',
                      }),
                      (0, e.jsxs)(c, {
                        variant: 'h6',
                        sx: {
                          color:
                            x.totalPnl >= 0 ? 'success.main' : 'error.main',
                        },
                        children: [
                          x.totalPnl >= 0 ? '+' : '',
                          x.totalPnl.toFixed(4),
                        ],
                      }),
                    ],
                  }),
                }),
              }),
              (0, e.jsx)(b, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(S, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(k, {
                    sx: { pb: 2 },
                    children: [
                      (0, e.jsx)(c, {
                        variant: 'caption',
                        color: 'text.secondary',
                        children: 'Total Positions',
                      }),
                      (0, e.jsx)(c, {
                        variant: 'h6',
                        children: x.totalPositions,
                      }),
                    ],
                  }),
                }),
              }),
              (0, e.jsx)(b, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(S, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(k, {
                    sx: { pb: 2 },
                    children: [
                      (0, e.jsx)(c, {
                        variant: 'caption',
                        color: 'text.secondary',
                        children: 'Equity (each model)',
                      }),
                      (0, e.jsx)(c, { variant: 'h6', children: '10' }),
                    ],
                  }),
                }),
              }),
            ],
          }),
          (0, e.jsxs)(j, {
            direction: 'row',
            spacing: 2,
            sx: { mb: 2 },
            alignItems: 'center',
            children: [
              (0, e.jsx)(ne, {
                size: 'small',
                placeholder: 'Search...',
                value: T,
                onChange: (t) => {
                  (V(t.target.value), M(0));
                },
                InputProps: {
                  startAdornment: (0, e.jsx)(ce, {
                    sx: { color: 'action.active', mr: 1, fontSize: 20 },
                  }),
                  endAdornment:
                    T &&
                    (0, e.jsx)(G, {
                      size: 'small',
                      onClick: () => V(''),
                      children: (0, e.jsx)(_, { fontSize: 'small' }),
                    }),
                },
                sx: { flexGrow: 1, maxWidth: 300 },
              }),
              (0, e.jsx)(I, { sx: { flexGrow: 1 } }),
              Object.keys(E).length > 0 &&
                (0, e.jsxs)(H, {
                  size: 'small',
                  onClick: () => R({}),
                  children: ['Show ', Object.keys(E).length, ' Hidden Rows'],
                }),
              (0, e.jsx)(H, {
                startIcon: (0, e.jsx)(le, {}),
                onClick: (t) => D(t.currentTarget),
                variant: 'outlined',
                size: 'small',
                children: 'Columns',
              }),
              (0, e.jsx)(ae, {
                open: !!q,
                anchorEl: q,
                onClose: () => D(null),
                anchorOrigin: { vertical: 'bottom', horizontal: 'right' },
                transformOrigin: { vertical: 'top', horizontal: 'right' },
                children: (0, e.jsxs)(I, {
                  sx: { p: 2, maxHeight: 300, overflow: 'auto' },
                  children: [
                    (0, e.jsx)(c, {
                      variant: 'subtitle2',
                      sx: { mb: 1 },
                      children: 'Visible Columns',
                    }),
                    (0, e.jsx)(j, {
                      children: f.map((t) =>
                        (0, e.jsx)(
                          se,
                          {
                            control: (0, e.jsx)(re, {
                              size: 'small',
                              checked: !!J[t],
                              onChange: () => me(t),
                            }),
                            label: t,
                          },
                          t
                        )
                      ),
                    }),
                  ],
                }),
              }),
            ],
          }),
          (0, e.jsx)(P, {
            component: ie,
            variant: 'outlined',
            children: (0, e.jsxs)(C, {
              size: 'small',
              children: [
                (0, e.jsx)(y, {
                  children: (0, e.jsxs)(p, {
                    sx: { bgcolor: 'action.hover' },
                    children: [
                      (0, e.jsx)(u, { sx: { width: 40 }, padding: 'none' }),
                      A.map((t) =>
                        (0, e.jsx)(
                          u,
                          {
                            sx: { fontWeight: 600 },
                            children: (0, e.jsx)(te, {
                              active: m === t,
                              direction: m === t ? w : 'asc',
                              onClick: () => ge(t),
                              children: t,
                            }),
                          },
                          t
                        )
                      ),
                    ],
                  }),
                }),
                (0, e.jsxs)(v, {
                  children: [
                    Y.map((t) =>
                      (0, e.jsxs)(
                        p,
                        {
                          hover: !0,
                          children: [
                            (0, e.jsx)(u, {
                              padding: 'none',
                              align: 'center',
                              children: (0, e.jsx)(G, {
                                size: 'small',
                                onClick: () => he(t),
                                sx: {
                                  opacity: 0.3,
                                  '&:hover': {
                                    opacity: 1,
                                    color: 'error.main',
                                  },
                                },
                                children: (0, e.jsx)(_, {
                                  fontSize: 'small',
                                  sx: { fontSize: 14 },
                                }),
                              }),
                            }),
                            A.map((s) => {
                              let l = t[s],
                                d =
                                  typeof l == 'string' &&
                                  /<\/?[a-z][\s\S]*>/i.test(l);
                              return (0, e.jsx)(
                                u,
                                {
                                  children: d
                                    ? (0, e.jsx)('div', {
                                        dangerouslySetInnerHTML: { __html: l },
                                      })
                                    : i?.formatUtcTime
                                      ? i.formatUtcTime(l)
                                      : (0, e.jsx)('div', { children: l }),
                                },
                                s
                              );
                            }),
                          ],
                        },
                        t.Identity || JSON.stringify(t)
                      )
                    ),
                    Y.length === 0 &&
                      (0, e.jsx)(p, {
                        children: (0, e.jsx)(u, {
                          colSpan: A.length + 1,
                          align: 'center',
                          sx: { py: 3 },
                          children: (0, e.jsx)(c, {
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
          (0, e.jsx)(oe, {
            component: 'div',
            count: O.length,
            page: L,
            rowsPerPage: z,
            rowsPerPageOptions: [10, 20, 50, 100],
            onPageChange: (t, s) => M(s),
            onRowsPerPageChange: (t) => {
              (pe(Number(t.target.value)), M(0));
            },
          }),
        ],
      })
    : (0, e.jsx)(c, { color: 'text.secondary', children: 'No data available' });
};
export { Be as default };
