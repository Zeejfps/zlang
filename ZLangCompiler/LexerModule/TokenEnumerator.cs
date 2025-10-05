using System.Collections;

namespace LexerModule;

internal sealed class TokenEnumerator : IEnumerator<Token>
{
    private Token _currentToken;
    
    private readonly Lexer _lexer;
    private readonly LexerStates _states;
    private ILexerState _state;

    private bool _isDisposed;

    public TokenEnumerator(TextReader reader)
    {
        _lexer = new Lexer(reader);
        _states = new LexerStates();
        _state = _states.FindNextTokenState;
    }

    public void Dispose()
    {
        if (!_isDisposed)
            return;

        _isDisposed = true;
        _lexer.Dispose();
        Console.WriteLine("Disposed");
    }

    public bool MoveNext()
    {
        if (_isDisposed)
            return false;
        
        Console.WriteLine($"MoveNext {_lexer.TokenCount}");
        while (_state != _states.EndOfFileState && _lexer.TokenCount == 0)
        {
            _state = _state.Update(_lexer);
        }
        
        Console.WriteLine($"After State Update: {_lexer.TokenCount}");
        if (_lexer.TryDequeueToken(out var token))
        {
            _currentToken = token;
            return true;
        }
        
        return false;
    }

    public void Reset()
    {
    }

    public Token Current => _currentToken;

    object? IEnumerator.Current => Current;
}