const UNITS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 365 * 24 * 3600],
    ["month", 30 * 24 * 3600],
    ["week", 7 * 24 * 3600],
    ["day", 24 * 3600],
    ["hour", 3600],
    ["minute", 60],
];

const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** "3 days ago", "last month", "just now": how long before `now` the date was. */
export const timeAgo = (date: string | Date, now: Date = new Date()): string => {
    const seconds = Math.round((new Date(date).getTime() - now.getTime()) / 1000);
    for (const [unit, length] of UNITS) {
        if (Math.abs(seconds) >= length) return formatter.format(Math.round(seconds / length), unit);
    }
    return "just now";
};
