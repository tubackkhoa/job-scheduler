function stdin_default({ useCallback, useState }, { Box, Button, TextField, Typography }, { buildJinjaContext }) {
  return function({ registry }) {
    const render = useCallback(
      buildJinjaContext(
        registry.formContext.pluginPackage,
        registry.formContext.env.filters,
        registry.formContext.formData
      ),
      [registry.formContext]
    );
    const [input, setInput] = useState(
      `{{ get_all_plugins() | tolist | tojson }}`
    );
    const [output, setOutput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const handleRun = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await render(input, {});
        setOutput(JSON.stringify(result, null, 2));
      } catch (err) {
        setError(err?.message ?? "Execution failed");
        setOutput("");
      } finally {
        setLoading(false);
      }
    };
    return /* @__PURE__ */ React.createElement(Box, { display: "flex", flexDirection: "column", gap: 2 }, /* @__PURE__ */ React.createElement(Typography, { variant: "subtitle1" }, "Jinja Input"), /* @__PURE__ */ React.createElement(
      TextField,
      {
        multiline: true,
        minRows: 4,
        value: input,
        onChange: (e) => setInput(e.target.value),
        fullWidth: true
      }
    ), /* @__PURE__ */ React.createElement(Button, { variant: "contained", onClick: handleRun, disabled: loading }, loading ? "Running\u2026" : "Run"), /* @__PURE__ */ React.createElement(Typography, { variant: "subtitle1" }, "Output (JSON)"), /* @__PURE__ */ React.createElement(
      TextField,
      {
        multiline: true,
        minRows: 6,
        value: output,
        fullWidth: true,
        InputProps: { readOnly: true }
      }
    ), error && /* @__PURE__ */ React.createElement(Typography, { color: "error" }, error));
  };
}
export {
  stdin_default as default
};
