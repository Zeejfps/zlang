namespace LexerModule;

public interface ITokenReader
{
    bool TryStartReading();
    Token FinishReading();
}