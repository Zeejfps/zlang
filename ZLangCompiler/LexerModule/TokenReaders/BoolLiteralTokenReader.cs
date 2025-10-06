namespace LexerModule.TokenReaders;

internal sealed class BoolLiteralTokenReader : ITokenReader
{
    private readonly Lexer _lexer;

    public BoolLiteralTokenReader(Lexer lexer)
    {
        _lexer = lexer;
    }

    public bool TryStartReading()
    {
        throw new NotImplementedException();
    }

    public Token FinishReading()
    {
        throw new NotImplementedException();
    }
}