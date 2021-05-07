export function parseBoolean(value: string | undefined, defaultValue: boolean = false): boolean {
    if (value == null) {
        return defaultValue;
    }
    switch (value.trim().toLowerCase()) {
        case 'true':
        case '1':
        case 'yes':
        case 'on':
            return true;
        case 'false':
        case '0':
        case 'no':
        case 'off':
            return false;
        default:
            throw new Error(`Invalid boolean value provided: ${JSON.stringify(value)}`);
    }
}
