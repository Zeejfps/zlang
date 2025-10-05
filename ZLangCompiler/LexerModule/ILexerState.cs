namespace LexerModule;

public interface ILexerState
{
    ILexerState Update(Lexer lexer);
}