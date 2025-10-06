namespace LexerModule;

public readonly record struct TwoCharSymbol(char FirstChar, char SecondChar)
{
    public static implicit operator TwoCharSymbol(string symbol)
        => new(symbol[0], symbol[1]);
    
    public static implicit operator TwoCharSymbol(Span<char> symbol)
        => new(symbol[0], symbol[1]);
}