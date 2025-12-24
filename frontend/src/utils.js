export const extractUiSchema = (schema) => {
  if (!schema || !schema.properties) return {};

  const uiSchema = {};
  const stack = [
    {
      props: schema.properties,
      target: uiSchema,
      path: []
    }
  ];

  while (stack.length > 0) {
    const { props, target, path } = stack.pop();

    for (const [key, prop] of Object.entries(props)) {
      const uiEntry = {};

      // Copy ui:field and ui:classNames if present
      for (const uiKey of ['ui:field', 'ui:classNames']) {
        if (prop[uiKey] !== undefined) {
          uiEntry[uiKey] = prop[uiKey];
        }
      }

      // Check for nested properties either inline or via $ref
      let nestedProps = null;

      if (prop.type === 'object' && prop.properties) {
        nestedProps = prop.properties;
      } else if (prop.$ref) {
        const defKey = prop.$ref.replace('#/$defs/', '');
        const defSchema = schema.$defs?.[defKey];
        if (defSchema?.type === 'object' && defSchema.properties) {
          nestedProps = defSchema.properties;
        }
      }

      // If nested properties exist, prepare for next iteration
      if (nestedProps) {
        // Add current uiEntry to target[key]
        target[key] = uiEntry;
        // Create the nested object to hold children UI schemas
        if (!target[key]) target[key] = {};
        // Stack push for deeper properties
        stack.push({
          props: nestedProps,
          target: target[key],
          path: [...path, key]
        });
      } else if (Object.keys(uiEntry).length > 0) {
        // Only add uiEntry if not empty and no nested props
        target[key] = uiEntry;
      }
    }
  }

  return uiSchema;
};

export const getSystemTheme = () =>
  window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
