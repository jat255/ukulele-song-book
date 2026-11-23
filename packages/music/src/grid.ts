/** Extract chord tokens inside bar lines, excluding beat and repeat markers. */
export function gridChords(text:string):string[] {
  return text.split(/\r\n|\r|\n/).flatMap(line => {
    const first=line.indexOf('|'), last=line.lastIndexOf('|');
    if (first<0 || last<=first) return [];
    return line.slice(first,last+1).split(/[\s|:]+/).flatMap(cell => cell.split('~')).filter(cell => !!cell && !/^(?:\.|\/|%+|\d+>?)$/.test(cell));
  });
}
