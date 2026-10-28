// Client-known operation vocabulary; availability is always declared by the server.
const serviceVocabulary = [
  "refresh",
  "start",
  "stop",
  "restart",
  "upgrade",
  "install",
  "uninstall",
  "doctor",
  "run",
];
export const serviceActions = (service) =>
  serviceVocabulary.filter((a) => service?.operations?.includes(a));
export const serviceAdapters = (data) =>
  data?.adapters?.interface_version === 1
    ? data.adapters.adapters.filter(
        (a) => a.kind === "service" && a.interface_version === 1,
      )
    : [];
export const backupApplications = (data) =>
  (data?.backup_applications || []).filter((a) =>
    a.operations.includes("backup"),
  );
export const canRestore = (backup) =>
  Boolean(backup?.operations?.includes("restore"));
export const isCommandOverride = (name) => /^cmd_(refresh|start|stop|restart|upgrade|install|uninstall|doctor|run)$/.test(name);
export function serviceBody(values) {
  return {
    name: values.name,
    host: values.host,
    adapter: values.adapter,
    settings: Object.fromEntries(
      Object.entries(values)
        .filter(([key]) => key.startsWith("settings."))
        .map(([key, value]) => [key.slice(9), value]),
    ),
  };
}

export function pluginSourceLabel(source) {
  return {builtin: "內建", github: "GitHub 官方", custom: "自訂", installed: "已安裝副本"}[source] || "本機";
}
export function pluginActionBody(plugin, action) {
  if (action !== "install" && action !== "update") return {action};
  return {action, version: plugin.version, ...(plugin.artifact_checksum ? {checksum: plugin.artifact_checksum} : {})};
}
