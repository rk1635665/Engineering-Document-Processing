export default function Card({
  title,
  icon: Icon,
  action,
  padding = "p-5",
  className = "",
  children,
}) {
  return (
    <div
      className={[
        "rounded-xl border border-line bg-white shadow-sm flex flex-col",
        className,
      ].join(" ")}
    >
      {(title || Icon || action) && (
        <div className="border-b border-line px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {Icon && (
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                <Icon size={16} strokeWidth={2} />
              </span>
            )}
            {title && (
              <h3 className="font-display text-sm font-semibold text-ink">
                {title}
              </h3>
            )}
          </div>
          {action}
        </div>
      )}
      <div className={padding}>{children}</div>
    </div>
  );
}