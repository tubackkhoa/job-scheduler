var me = Object.create;
var D = Object.defineProperty;
var ye = Object.getOwnPropertyDescriptor;
var be = Object.getOwnPropertyNames;
var Te = Object.getPrototypeOf,
  xe = Object.prototype.hasOwnProperty;
var W = (r, n) => () => (n || r((n = { exports: {} }).exports, n), n.exports);
var Ce = (r, n, o, a) => {
  if ((n && typeof n == 'object') || typeof n == 'function')
    for (let l of be(n))
      !xe.call(r, l) &&
        l !== o &&
        D(r, l, {
          get: () => n[l],
          enumerable: !(a = ye(n, l)) || a.enumerable,
        });
  return r;
};
var Y = (r, n, o) => (
  (o = r != null ? me(Te(r)) : {}),
  Ce(
    n || !r || !r.__esModule
      ? D(o, 'default', { value: r, enumerable: !0 })
      : o,
    r
  )
);
var Q = W((k) => {
  'use strict';
  var fe = Symbol.for('react.transitional.element'),
    ve = Symbol.for('react.fragment');
  function $(r, n, o) {
    var a = null;
    if (
      (o !== void 0 && (a = '' + o),
      n.key !== void 0 && (a = '' + n.key),
      'key' in n)
    ) {
      o = {};
      for (var l in n) l !== 'key' && (o[l] = n[l]);
    } else o = n;
    return (
      (n = o.ref),
      { $$typeof: fe, type: r, key: a, ref: n !== void 0 ? n : null, props: o }
    );
  }
  k.Fragment = ve;
  k.jsx = $;
  k.jsxs = $;
});
var B = W((Ee, U) => {
  'use strict';
  U.exports = Q();
});
var e = Y(B(), 1);
function w(r) {
  if (typeof r == 'number') return r;
  if (typeof r == 'string') {
    let o = r.replace(/<[^>]*>/g, '').replace(/[^\d.-]/g, ''),
      a = parseFloat(o);
    return isNaN(a) ? 0 : a;
  }
  return 0;
}
function X(r, n, o) {
  let a = w(r[o]),
    l = w(n[o]);
  if (a !== 0 || l !== 0) return l < a ? -1 : l > a ? 1 : 0;
  let x = String(r[o] ?? '').toLowerCase(),
    d = String(n[o] ?? '').toLowerCase();
  return d < x ? -1 : d > x ? 1 : 0;
}
function Pe(r, n) {
  return r === 'desc' ? (o, a) => X(o, a, n) : (o, a) => -X(o, a, n);
}
var Le = ({ formData: r, Mui: n, React: o, MuiIcon: a }) => {
  let {
      Table: l,
      TableBody: x,
      TableCell: d,
      TableContainer: Z,
      TableHead: K,
      TableRow: z,
      TableSortLabel: ee,
      TablePagination: te,
      TextField: oe,
      Box: E,
      Checkbox: ne,
      FormControlLabel: re,
      Stack: j,
      IconButton: A,
      Button: F,
      Card: C,
      CardContent: f,
      Typography: c,
      Grid: g,
      Popover: se,
      Paper: ae,
      Divider: Se,
      MenuItem: ke,
    } = n,
    { ViewColumn: le, FilterList: ie, Clear: G } = a,
    [v, ce] = o.useState('desc'),
    [h, de] = o.useState('Total PNL'),
    [m, H] = o.useState(''),
    [L, N] = o.useState(0),
    [P, ue] = o.useState(10),
    [_, R] = o.useState(null),
    [S, V] = o.useState({}),
    u = o.useMemo(() => {
      if (!r) return [];
      try {
        let t = JSON.parse(r);
        return Array.isArray(t) ? t : [];
      } catch {
        return [];
      }
    }, [r]),
    y = o.useMemo(() => (u.length === 0 ? [] : Object.keys(u[0])), [u]),
    [O, q] = o.useState({});
  o.useEffect(() => {
    if (y.length > 0 && Object.keys(O).length === 0) {
      let t = y.reduce((s, i) => ((s[i] = !0), s), {});
      q(t);
    }
  }, [y]);
  let b = o.useMemo(() => {
      if (!u) return [];
      let t = u;
      if (((t = t.filter((s) => !S[s.Identity || s.id])), m)) {
        let s = m.toLowerCase();
        t = t.filter((i) =>
          Object.values(i).some((p) => String(p).toLowerCase().includes(s))
        );
      }
      return t;
    }, [u, m, S]),
    I = o.useMemo(() => [...b].sort(Pe(v, h)), [b, v, h]),
    J = o.useMemo(() => {
      let t = L * P;
      return I.slice(t, t + P);
    }, [I, L, P]),
    T = o.useMemo(() => {
      let t = b.length,
        s = 0,
        i = 0;
      return (
        b.forEach((p) => {
          ((s += w(p['Total PNL'])), (i += w(p['Total Positions'])));
        }),
        { totalModels: t, totalPnl: s, totalPositions: i }
      );
    }, [b]),
    pe = (t) => {
      (ce(h === t && v === 'asc' ? 'desc' : 'asc'), de(t));
    },
    ge = (t) => {
      q((s) => ({ ...s, [t]: !s[t] }));
    },
    he = (t) => {
      let s = t.Identity || JSON.stringify(t);
      V((i) => ({ ...i, [s]: !0 }));
    },
    M = y.filter((t) => O[t]);
  return u.length
    ? (0, e.jsxs)(E, {
        children: [
          (0, e.jsxs)(g, {
            container: !0,
            spacing: 2,
            sx: { mb: 2 },
            children: [
              (0, e.jsx)(g, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(C, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(f, {
                    sx: { pb: 2 },
                    children: [
                      (0, e.jsx)(c, {
                        variant: 'caption',
                        color: 'text.secondary',
                        children: 'Total models',
                      }),
                      (0, e.jsx)(c, { variant: 'h6', children: T.totalModels }),
                    ],
                  }),
                }),
              }),
              (0, e.jsx)(g, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(C, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(f, {
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
                            T.totalPnl >= 0 ? 'success.main' : 'error.main',
                        },
                        children: [
                          T.totalPnl >= 0 ? '+' : '',
                          T.totalPnl.toFixed(4),
                        ],
                      }),
                    ],
                  }),
                }),
              }),
              (0, e.jsx)(g, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(C, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(f, {
                    sx: { pb: 2 },
                    children: [
                      (0, e.jsx)(c, {
                        variant: 'caption',
                        color: 'text.secondary',
                        children: 'Total Positions',
                      }),
                      (0, e.jsx)(c, {
                        variant: 'h6',
                        children: T.totalPositions,
                      }),
                    ],
                  }),
                }),
              }),
              (0, e.jsx)(g, {
                size: { xs: 6, md: 3 },
                children: (0, e.jsx)(C, {
                  sx: { bgcolor: 'background.paper', height: '100%' },
                  children: (0, e.jsxs)(f, {
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
              (0, e.jsx)(oe, {
                size: 'small',
                placeholder: 'Search...',
                value: m,
                onChange: (t) => {
                  (H(t.target.value), N(0));
                },
                InputProps: {
                  startAdornment: (0, e.jsx)(ie, {
                    sx: { color: 'action.active', mr: 1, fontSize: 20 },
                  }),
                  endAdornment:
                    m &&
                    (0, e.jsx)(A, {
                      size: 'small',
                      onClick: () => H(''),
                      children: (0, e.jsx)(G, { fontSize: 'small' }),
                    }),
                },
                sx: { flexGrow: 1, maxWidth: 300 },
              }),
              (0, e.jsx)(E, { sx: { flexGrow: 1 } }),
              Object.keys(S).length > 0 &&
                (0, e.jsxs)(F, {
                  size: 'small',
                  onClick: () => V({}),
                  children: ['Show ', Object.keys(S).length, ' Hidden Rows'],
                }),
              (0, e.jsx)(F, {
                startIcon: (0, e.jsx)(le, {}),
                onClick: (t) => R(t.currentTarget),
                variant: 'outlined',
                size: 'small',
                children: 'Columns',
              }),
              (0, e.jsx)(se, {
                open: !!_,
                anchorEl: _,
                onClose: () => R(null),
                anchorOrigin: { vertical: 'bottom', horizontal: 'right' },
                transformOrigin: { vertical: 'top', horizontal: 'right' },
                children: (0, e.jsxs)(E, {
                  sx: { p: 2, maxHeight: 300, overflow: 'auto' },
                  children: [
                    (0, e.jsx)(c, {
                      variant: 'subtitle2',
                      sx: { mb: 1 },
                      children: 'Visible Columns',
                    }),
                    (0, e.jsx)(j, {
                      children: y.map((t) =>
                        (0, e.jsx)(
                          re,
                          {
                            control: (0, e.jsx)(ne, {
                              size: 'small',
                              checked: !!O[t],
                              onChange: () => ge(t),
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
          (0, e.jsx)(Z, {
            component: ae,
            variant: 'outlined',
            children: (0, e.jsxs)(l, {
              size: 'small',
              children: [
                (0, e.jsx)(K, {
                  children: (0, e.jsxs)(z, {
                    sx: { bgcolor: 'action.hover' },
                    children: [
                      (0, e.jsx)(d, { sx: { width: 40 }, padding: 'none' }),
                      M.map((t) =>
                        (0, e.jsx)(
                          d,
                          {
                            sx: { fontWeight: 600 },
                            children: (0, e.jsx)(ee, {
                              active: h === t,
                              direction: h === t ? v : 'asc',
                              onClick: () => pe(t),
                              children: t,
                            }),
                          },
                          t
                        )
                      ),
                    ],
                  }),
                }),
                (0, e.jsxs)(x, {
                  children: [
                    J.map((t) =>
                      (0, e.jsxs)(
                        z,
                        {
                          hover: !0,
                          children: [
                            (0, e.jsx)(d, {
                              padding: 'none',
                              align: 'center',
                              children: (0, e.jsx)(A, {
                                size: 'small',
                                onClick: () => he(t),
                                sx: {
                                  opacity: 0.3,
                                  '&:hover': {
                                    opacity: 1,
                                    color: 'error.main',
                                  },
                                },
                                children: (0, e.jsx)(G, {
                                  fontSize: 'small',
                                  sx: { fontSize: 14 },
                                }),
                              }),
                            }),
                            M.map((s) => {
                              let i = t[s],
                                p =
                                  typeof i == 'string' &&
                                  /<\/?[a-z][\s\S]*>/i.test(i);
                              return (0, e.jsx)(
                                d,
                                {
                                  children: p
                                    ? (0, e.jsx)('div', {
                                        dangerouslySetInnerHTML: { __html: i },
                                      })
                                    : i,
                                },
                                s
                              );
                            }),
                          ],
                        },
                        t.Identity || JSON.stringify(t)
                      )
                    ),
                    J.length === 0 &&
                      (0, e.jsx)(z, {
                        children: (0, e.jsx)(d, {
                          colSpan: M.length + 1,
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
          (0, e.jsx)(te, {
            component: 'div',
            count: I.length,
            page: L,
            rowsPerPage: P,
            rowsPerPageOptions: [10, 20, 50, 100],
            onPageChange: (t, s) => N(s),
            onRowsPerPageChange: (t) => {
              (ue(Number(t.target.value)), N(0));
            },
          }),
        ],
      })
    : (0, e.jsx)(c, { color: 'text.secondary', children: 'No data available' });
};
export { Le as default };
