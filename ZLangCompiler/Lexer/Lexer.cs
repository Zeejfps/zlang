namespace LexerModule;

public class Lexer
{
    public ILexerState ProcessWordTokenState { get; } = new ProcessWordTokenState();
    public ILexerState FindNextTokenState { get; } = new FindNextTokenState();
    public ILexerState ReadOperatorTokenState { get; } = new ReadOperatorTokenState();
    public ILexerState ReadWordTokenState { get; } = new ReadWordTokenState();

    public Span<char> Lexeme => _buffer.AsSpan();

    private char[] _buffer;
    
    public char PeekChar()
    {
        return ' ';
    }
    
    public static IEnumerable<Token> Tokenize(string empty)
    {
        using var reader = new StringReader(empty);
        foreach (var token in Tokenize(reader))
            yield return token;
    }

    public static IEnumerable<Token> Tokenize(TextReader reader)
    {
        var buffer = new char[256];
        var writeIndex = 0;
        var line = 1;
        var column = 1;
        int c;
        while ((c = reader.Peek()) != -1)
        {
            if (c == ' ')
            {
                var lexeme = buffer.AsSpan(0, writeIndex).ToString();
                if (lexeme == "module")
                {
                    yield return new Token(TokenKind.ModuleKeyWord, lexeme, line, column);
                }
                else
                {
                    yield return new Token(TokenKind.Identifier, lexeme, line, column);
                }

                column += writeIndex + 1;
                writeIndex = 0;
                continue;
            }

            if (c == '=')
            {
                yield return new Token(TokenKind.Equals, "=", line, column);
                column += 1;
                writeIndex = 0;
                continue;
            }
            
            buffer[writeIndex] = (char)c;
            writeIndex++;
        }
        
        yield return new Token(TokenKind.Eof,  string.Empty, line, column);
    }

    public void WriteChar(int c)
    {
        throw new NotImplementedException();
    }

    public char ReadChar()
    {
        throw new NotImplementedException();
    }
}

public interface ILexerState
{
    ILexerState Update(Lexer lexer);
}


public sealed class ReadWordTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == ' ' || nextChar == '=')
        {
            return lexer.ProcessWordTokenState;
        }
        
        var c = lexer.ReadChar();
        lexer.WriteChar(c);
        return this;
    }
}

public sealed class ProcessWordTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var lexeme = lexer.Lexeme;
        if (lexeme is "module")
        {
            
        }

        return lexer.FindNextTokenState;
    }
}

public sealed class FindNextTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        var nextChar = lexer.PeekChar();
        if (nextChar == '=')
        {
            return lexer.ReadOperatorTokenState;
        }

        if (char.IsLetter(nextChar))
        {
            return lexer.ReadWordTokenState;
        }

        lexer.ReadChar();
        return this;
    }
}

public sealed class ReadOperatorTokenState : ILexerState
{
    public ILexerState Update(Lexer lexer)
    {
        throw new NotImplementedException();
    }
}